from abc import ABC, abstractmethod

from Levenshtein import distance

from models import Protein
from models import Gene
from sqlalchemy import and_


class GeneMatch:

    def __init__(self, gene=None, scored_matches=None, matched_isoforms=None):
        self.gene = gene
        self.matches = scored_matches or {}
        self.matched_isoforms = matched_isoforms or []

    @classmethod
    def from_feature(cls, gene, matched_feature, match_score, matched_isoforms=None):
        return cls(gene, {matched_feature: match_score}, matched_isoforms)

    @property
    def best_score(self):
        return max(self.matches.values())

    def __iadd__(self, other):
        if not self.gene:
            self.gene = other.gene

        assert self.gene == other.gene

        for feature, score in other.matches.items():
            my_score = self.matches.get(feature, 0)
            self.matches[feature] = max(my_score, score)

        self.matched_isoforms.extend(other.matched_isoforms)

        return self

    def __getattr__(self, key):
        return getattr(self.gene, key)


class GeneSearch(ABC):

    @abstractmethod
    def search(self, phase, limit=None):
        pass


class RefseqGeneSearch(GeneSearch):

    name = 'refseq'

    def search(self, phase, sql_filters=None, limit=None):

        if phase.isnumeric():
            phase = 'NM_' + phase

        if not (phase.startswith('NM_') or phase.startswith('nm_')):
            return []

        matches = []

        filters = [Protein.refseq.like(phase + '%')]

        if sql_filters:
            filters += sql_filters

        query = Protein.query.filter(and_(*filters))

        if limit:
            # we want to display up to 'limit' genes;
            # still it would be good to restrict isoforms
            # query in such way then even when getting
            # results where all isoforms match the same
            # gene it still provides more than one gene
            query = query.limit(limit * 20)

        for isoform in query:
            if limit and len(matches) > limit:
                break

            gene = isoform.gene

            match = GeneMatch.from_feature(
                gene,
                self.name,
                self.sort_key(isoform, phase),
                matched_isoforms={isoform}
            )
            matches.append(match)

        return matches

    @staticmethod
    def sort_key(isoform, phase):
        return distance(isoform.refseq, phase)


class SymbolGeneSearch(GeneSearch):

    name = 'gene_symbol'

    def search(self, phase, sql_filters=None, limit=None):

        filters = [Gene.name.like(phase + '%')]

        if sql_filters:
            filters += sql_filters

        orm_query = (
            Gene.query
                .join(Protein, Gene.preferred_isoform)   # to allow PTM filter
                .filter(and_(*filters))
        )

        if limit:
            orm_query = orm_query.limit(limit)

        return [
            GeneMatch.from_feature(gene, self.name, self.sort_key(gene, phase))
            for gene in orm_query
        ]

    @staticmethod
    def sort_key(gene, phase):
        return distance(gene.name, phase)


feature_engines = {
    RefseqGeneSearch,
    SymbolGeneSearch,
}

search_features = {
    engine.name: engine()
    for engine in feature_engines
}
