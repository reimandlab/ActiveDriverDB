import re
from tempfile import NamedTemporaryFile
from pathlib import Path
from base64 import b64encode
from typing import Dict, Counter

import networkx
from collections.__init__ import defaultdict
from functools import lru_cache

import obonet as obonet
from Levenshtein._levenshtein import ratio
from matplotlib import colors
from matplotlib.cm import get_cmap
from networkx.drawing import nx_agraph
from numpy import percentile
from sklearn.feature_extraction.text import TfidfVectorizer
from tqdm import tqdm

from helpers.commands import get_answer
from helpers.cache import Cache


def choose_best_match(ontology, term, candidates, history=[]):

    grand_parent_level = max(len(history) - 1, 0)

    parent = '' if not history else (
        'grand ' * grand_parent_level + 'parent '
    )

    choices = {}
    choices_presentation = []

    if history:
        choices[-2] = 'get-back'
        choices_presentation.append('-2. Return to children of the presented nodes')

    choices[-1] = 'show-me-parents'
    choices[0] = None

    choices_presentation.extend(['-1. Show me parent nodes of the presented choices', ' 0. None of presented'])

    i = 0
    for name, (node, mode) in candidates.items():
        i += 1
        choices[i] = name
        choices_presentation.append(f' {i}. {name}\t{mode}')

    name = get_answer(
        (
            f'Following {parent}nodes might correspond to "{term}":\n'
            + "\n".join(choices_presentation) +
            f'\nWhich one to use? '
        ),
        choices
    )

    if name == 'show-me-parents':
        parents = {}

        for node, mode in candidates.values():
            for parent in ontology.out_edges[node]:
                name = ontology.nodes[parent]['name']
                parents[name] = (parent, mode)
        return choose_best_match(ontology, term, parents, history + [candidates])
    elif name == 'get-back':
        return choose_best_match(ontology, term, history[-1], history[:-1])
    elif name:
        node = candidates[name][0]
        return node


def simplify(name):
    return name.lower().replace(' type ', ' ').replace(' form ', ' ').replace(',', '')


def compare(term, name):
    return ratio(simplify(term), simplify(name))


cache = Cache('.ontology_cache')


class Ontology:

    def __init__(self, obo_path):
        self.ontology = obonet.read_obo(obo_path)
        # initialize cached propertry with side effects
        self.by_name

    @property
    @lru_cache()
    def by_name(self):

        nodes_by_name = {}

        for node_id, data in self.ontology.nodes(data=True):
            if 'name' in data:
                name = data['name']
                nodes_by_name[name] = node_id
            elif node_id.startswith('https://rarediseases.info.nih.gov/diseases/'):
                name = node_id.split('/')[-1].replace('-', ' ')
                data['name'] = name
                nodes_by_name[name] = node_id
            else:
                print(f'No name for node: {node_id}')

        return nodes_by_name

    @property
    @lru_cache()
    def by_xrefs(self):

        nodes_by_xref = {}

        for node_id, data in self.ontology.nodes(data=True):
            if 'xref' in data:
                for xref in data['xref']:
                    nodes_by_xref[xref] = node_id

        return nodes_by_xref

    @property
    @lru_cache()
    def out_edges(self):
        out_edges = defaultdict(list)
        out_edge_modifiers = {}
        for f, t, *l in self.ontology.in_edges:

            out_edges[t].append(f)
            out_edge_modifiers[t, f] = l

        self.out_edge_modifiers = out_edge_modifiers

        return out_edges

    @property
    @lru_cache()
    def in_edges(self):
        # workaround for networkx bug when some edges have labels and some have not:
        in_edges = defaultdict(list)
        edge_modifiers = {}
        for f, t, *l in self.ontology.in_edges:

            # look out for is_not labels!
            for relation in l:
                assert 'not' not in relation

            in_edges[t].append(f)
            edge_modifiers[t, f] = l

        self.edge_modifiers = edge_modifiers

        return in_edges

    @lru_cache(maxsize=2000)
    def is_descendant_of(self, tested_node_id, ancestor_id, accepted_relations=('is_a', )):

        nodes_to_check = {tested_node_id}
        visited = set()

        while nodes_to_check:
            node_id = nodes_to_check.pop()
            visited.add(node_id)
            if node_id == ancestor_id:
                return True
            nodes_to_check.update([
                n for n in self.in_edges[node_id]
                if n not in visited and any(
                    mod in accepted_relations
                    for mod in self.edge_modifiers[node_id, n]
                )
            ])

        return False

    def __getattr__(self, item):
        return getattr(self.ontology, item)

    def find_terms(self, terms: Dict[str, int], allow_misses=True, re_run=False, show_progress=False) -> Dict[str, int]:
        detected_nodes = Counter()
        missed_terms = set()

        print(f'Searching for {len(terms)} terms in {self.name} ontology')

        vec = TfidfVectorizer()

        terms_items = tqdm(terms.items(), total=len(terms)) if show_progress else terms.items()

        for term, count in terms_items:
            cache_key = (self.name, term)
            if not re_run and cache_key in cache:
                chosen_nodes = cache[cache_key]
            else:
                chosen_nodes = self.by_name.get(term, None)
                if not chosen_nodes:
                    candidates = {}

                    # look fo synonyms and partial matches
                    for node in self.nodes:
                        data = self.nodes[node]
                        if not data:
                            continue
                        name = data['name']

                        if term.lower() == name.lower():
                            chosen_nodes = node
                            break

                        for synonym in data.get('synonym', []):
                            match = re.match('"(.*?)" (.*?) \[.*\]', synonym)
                            synonym_name, similarity = match.group(1, 2)
                            if synonym_name.lower() == term.lower():
                                if similarity in ['EXACT', 'NARROW']:
                                    print(f'"{term}" matched as synonym of {name}')
                                    chosen_nodes = node
                                    break
                                else:
                                    candidates[name] = (node, f'{similarity} synonym')
                            elif compare(term, synonym_name) > 0.8:
                                candidates[name] = (node, f'{similarity} synonym ({synonym_name})')

                        if chosen_nodes:
                            break

                        score = compare(term, name)

                        mode = None

                        if score > 0.95:
                            mode = 'very similar'
                        elif score > 0.9:
                            mode = 'quite similar'
                        elif score > 0.8:
                            mode = 'similar'
                        elif compare_generalized(term, name) > 0.8:
                            mode = 'more general'
                        elif score > 0.4:
                            vectorizer = vec.fit_transform([term.lower(), name.lower()])
                            similarity = vectorizer * vectorizer.T
                            if similarity[0, 1] > 0.5:
                                print(similarity[0, 1], score)
                                mode = 'cosine similarity'

                        if mode:
                            candidates[name] = (node, mode)

                    if not chosen_nodes and candidates:
                        candidates = {
                            name: candidates[name]
                            for name in sorted(
                                candidates,
                                key=lambda n: compare(term, n),
                                reverse=True
                            )
                        }
                        chosen_nodes = choose_best_match(self, term, candidates)

                    if not allow_misses and not chosen_nodes:
                        while not chosen_nodes:
                            print(f'Could not find node for {term}.')
                            node_ids = input(
                                'As misses are not allowed, please specify the node manually '
                                '(you may give more than one node, separating with ","): '
                                # to enable use of "Pheochromocytoma and Paraganglioma"
                            )
                            node_ids = node_ids.split(',')
                            match = True
                            for node_id in node_ids:
                                if node_id not in self.nodes:
                                    print(f'{node_id} is not a member of this ontology')
                                    match = False

                            if match:
                                chosen_nodes = node_ids

                        for node_id in chosen_nodes:
                            data = self.nodes[node_id]
                            print(f'You chose {data["name"]} manually for {term}')

                    cache[cache_key] = chosen_nodes

            if not chosen_nodes:
                missed_terms.add(term)
                continue
            else:
                if isinstance(chosen_nodes, str):
                    chosen_nodes = [chosen_nodes]
                per_node_count = count / len(chosen_nodes)
                for node_id in chosen_nodes:
                    detected_nodes[node_id] += per_node_count

        found = len(terms) - len(missed_terms)
        print(f'Mapped {found} terms to {len(detected_nodes)} nodes ({found / len(terms) * 100:.2f}% of terms mapped)')
        # without_hemoglobin = [
        #     t for t in terms.keys()
        #     if not t.lower().startswith("hemoglobin")
        # ]
        # print(f'{found / len(without_hemoglobin) * 100}% when ignoring hemoglobin types')
        return detected_nodes

    def propagate_terms_counts(self, starting_nodes):
        propagated_terms = Counter()# defaultdict(int)

        for starting_node, count in starting_nodes.items():

            visited = set()
            next_nodes = [starting_node]
            while next_nodes:

                nodes = next_nodes
                next_nodes = set()
                for node in nodes:

                    visited.add(node)
                    data = self.nodes[node]

                    if data:
                        propagated_terms[data['name']] += count
                    else:
                        # not a known issue
                        if not node.startswith('https://github.com/NCI-Thesaurus/thesaurus-obo-edition/issues'):
                            print(f'No data for {node}')

                    candidate_nodes = [
                        node
                        for current_node, node in self.ontology.out_edges(node)
                        if not (node in visited or node in next_nodes or node in nodes)
                    ]

                    next_nodes.update(candidate_nodes)

        return propagated_terms

    def find_by_xrefs(self, terms, show_progress=False, verbose=True):
        terms_items = (
            tqdm(terms.items(), total=len(terms))
            if show_progress else
            terms.items()
        )
        detected_nodes = {
            self.by_xrefs[term]: count
            for term, count in terms_items
            if term in self.by_xrefs
        }
        if verbose:
            print(f'Mapped {len(detected_nodes)} (or {len(detected_nodes)  / len(terms) * 100:.2f}%) of {len(terms)} terms')
        return detected_nodes

    def process_graph(self, terms, include_above_percentile=0, root_name=None, color_map_name=None, allow_misses=True, show_all_terms=False, xrefs=False, show_progress=False):

        if not xrefs:
            nodes_of_mapped_terms = self.find_terms(terms, allow_misses=allow_misses, show_progress=show_progress)
        else:
            nodes_of_mapped_terms = self.find_by_xrefs(terms, show_progress=show_progress)

        counts = self.propagate_terms_counts(nodes_of_mapped_terms)

        terms_to_include = self.select_terms(counts, include_above_percentile, root_name)

        return self.subgraph_for_drawing(terms_to_include, nodes_of_mapped_terms, counts, color_map_name=color_map_name)

    def select_terms(self, counts, include_above_percentile=0, root_name=None):

        terms_to_include = []

        root = self.by_name[root_name] if root_name else None

        p_all = None

        if include_above_percentile:
            p_all = percentile(list(counts.values()), include_above_percentile)
            # p_terms = percentile(list(nodes.values()), include_above_percentile - 5)

        terms_to_include += [
            term for term, count in counts.items()
            if (
                    (not root or self.is_descendant_of(root, self.by_name[term]))
                    and
                    (not include_above_percentile or (
                        (count > p_all)
                        #if not show_all_terms else
                        #(True if term in nodes_of_mapped_terms else count > p_all)
                    ))
            )
        ]

        if not terms_to_include:
            print(f'No nodes above {include_above_percentile} percentile for {root_name} root')
            return terms_to_include

        return terms_to_include

    def subgraph_for_drawing(self, terms_to_include, nodes_of_mapped_terms, counts, color_map_name=None):

        g = self.subgraph([
            node for node, data in self.nodes(data=True) if data.get('name', None) in terms_to_include
        ])
        g = g.reverse()

        if not g.nodes():
            return g

        graph_counts = {node: counts[data['name']] for node, data in g.nodes(data=True)}

        norm = colors.LogNorm(min(graph_counts.values()), max(graph_counts.values()))

        color_map = get_cmap(color_map_name) if color_map_name else None

        for node in g.nodes:
            node_graphics = g.node[node]

            n = norm(graph_counts[node])
            color = color_map(n) if color_map else (1, 1 - n / 4, 1 - n / 2)

            node_graphics['fillcolor'] = colors.to_hex(color)
            node_graphics['shape'] = 'box'
            node_graphics['style'] = 'bold,filled' if node in nodes_of_mapped_terms else 'dashed,filled'

        g = networkx.nx.relabel_nodes(
            g,
            {
                node: data['name'] + f': {graph_counts[node]:g}'
                for node, data in g.nodes(data=True)
            }
        )
        return g


def compare_generalized(term, name):
    term = term.lower().replace('congenital', '').replace('familial', '')
    return compare(name.replace('(disease)', ''), term)


class OntologyPlot:

    def __init__(self, path, embed=True):
        self.path = path
        self.embed = embed

    def _repr_html_(self):
        if self.embed:
            with open(self.path, 'rb') as f:
                encoded = str(b64encode(f.read())).lstrip('b\'').rstrip('\'')
                return f'<img src="data:image/png;base64,{encoded}">'

        return f'<img src="{self.path}">'


def draw_ontology_graph(g, path=None, unflatten=900, embed=True):
    a = nx_agraph.to_agraph(g)

    if len(g.nodes) < 20:
        unflatten = 0

    if unflatten:
        a.unflatten(f'-l {unflatten} -f')
    a.layout('dot', args='-Nfontsize=14 -Nwidth=".2" -Nheight=".2" -Nmargin=.1 -Gfontsize=8 -Earrowsize=.5')

    if path:
        return a.draw(str(path))
    else:

        dir_path = Path('images')
        dir_path.mkdir(exist_ok=True)
        temp_file = NamedTemporaryFile(delete=False, dir=dir_path, suffix='.png')
        temp_file.close()
        a.draw(temp_file.name)
        relative_path = Path(temp_file.name).relative_to(dir_path.parent.absolute())

        return OntologyPlot(relative_path, embed)
