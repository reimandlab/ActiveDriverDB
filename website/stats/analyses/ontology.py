import re
from typing import Dict, Counter

import networkx
from collections.__init__ import defaultdict
from functools import lru_cache

import obonet as obonet
from Levenshtein._levenshtein import ratio
from diskcache import Cache
from matplotlib import colors
from matplotlib.cm import get_cmap
from networkx.drawing import nx_agraph
from numpy import percentile

from helpers.commands import get_answer


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

    def find_terms(self, terms: Dict[str, int]) -> Dict[str, int]:
        detected_nodes = {}

        for term, count in terms.items():
            cache_key = (self.name, term)
            if cache_key in cache:
                chosen_node = cache[cache_key]
            else:
                chosen_node = self.by_name.get(term, None)
                if not chosen_node:
                    candidates = {}

                    # look fo synonyms and partial matches
                    for node in self.nodes:
                        data = self.nodes[node]
                        if not data:
                            continue
                        name = data['name']

                        if term.lower() == name.lower():
                            chosen_node = node
                            break

                        for synonym in data.get('synonym', []):
                            if term in synonym:
                                match = re.match('"(.*?)" (.*?) \[.*\]', synonym)
                                synonym_name, similarity = match.group(1, 2)
                                if synonym_name == term:
                                    if similarity in ['EXACT', 'NARROW']:
                                        print(f'"{term}" matched as synonym of {name}')
                                        chosen_node = node
                                        break
                                    else:
                                        candidates[name] = (node, f'{similarity} synonym')

                        if chosen_node:
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

                        if mode:
                            candidates[name] = (node, mode)

                    if not chosen_node and candidates:
                        candidates = {
                            name: candidates[name]
                            for name in sorted(
                                candidates,
                                key=lambda n: compare(term, n),
                                reverse=True
                            )
                        }
                        chosen_node = choose_best_match(self, term, candidates)

                    cache[cache_key] = chosen_node

            if not chosen_node:
                continue
            else:
                detected_nodes[chosen_node] = count
        found = len(detected_nodes)
        print(f'Detected {found} terms, {found / len(terms) * 100}%')
        without_hemoglobin = [
            t for t in terms.keys()
            if not t.lower().startswith("hemoglobin")
        ]
        print(f'{found / len(without_hemoglobin) * 100}% when ignoring hemoglobin types')
        return detected_nodes

    def propagate_terms_counts(self, starting_nodes):
        propagated_terms = Counter()

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
                        name = data['name']
                        propagated_terms[name] += count
                    else:
                        print(f'No data for {node} {name}')

                    candidate_nodes = {
                        node
                        for current_node, node in self.out_edges(node)
                        if not (node in visited or node in next_nodes or node in nodes)
                    }

                    next_nodes.update(candidate_nodes)

        return propagated_terms

    def process_graph(self, terms, include_above_percentile=0, root_name=None, color_map_name=None):

        nodes_of_mapped_terms = self.find_terms(terms)
        counts = self.propagate_terms_counts(nodes_of_mapped_terms)

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
                            count > p_all
                        # count > p_terms if term in nodes_of_mapped_terms else count > p_all
                    ))
            )
        ]

        g = self.subgraph([
            node for node, data in self.nodes(data=True) if data.get('name', None) in terms_to_include
        ])
        g = g.reverse()

        graph_counts = {node: counts[data['name']] for node, data in g.nodes(data=True)}

        norm = colors.LogNorm(min(graph_counts.values()), max(graph_counts.values()))

        color_map = get_cmap(color_map_name) if color_map_name else None

        for node in g.nodes:
            node_graphics = g.node[node]

            n = norm(graph_counts[node])
            color = color_map(n) if color_map else (1, 1 - n / 2, 1 - n / 2)

            node_graphics['fillcolor'] = colors.to_hex(color)
            node_graphics['shape'] = 'box'
            node_graphics['style'] = 'bold,filled' if node in nodes_of_mapped_terms else 'dashed,filled'

        g = networkx.nx.relabel_nodes(g, {node: data['name'] + f': {graph_counts[node]}' for node, data in g.nodes(data=True)})
        return g


def compare_generalized(term, name):
    term = term.lower().replace('congenital', '').replace('familial', '')
    return compare(name.replace('(disease)', ''), term)


def draw_ontology_graph(g, path):
    a = nx_agraph.to_agraph(g)

    a.unflatten('-l 900 -f')
    a.layout('dot', args='-Nfontsize=14 -Nwidth=".2" -Nheight=".2" -Nmargin=.1 -Gfontsize=8 -Earrowsize=.5')
    a.draw(path)

    return a
