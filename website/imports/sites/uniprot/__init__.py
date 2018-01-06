"""UniProt sites are retrieved using online SPARQL endpoint.

UniProt divides PTM sites into four categories:
- lipids (lipidations)
- glycans (glycosylation, glycation)
- cross-links (ubiquitination, sumoylation, etc.)
- all others (phosphorylation, methylation, acetylation, etc.)

References:
    http://www.uniprot.org/help/mod_res
    http://www.uniprot.org/docs/ptmlist
"""

from .others import OthersUniprotImporter
from .glycans import GlycosylationUniprotImporter

__all__ = [OthersUniprotImporter, GlycosylationUniprotImporter]
