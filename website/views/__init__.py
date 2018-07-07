from .protein import ProteinView
from .gene import GeneView
from .search import SearchView
from .sequence import SequenceView
from .network import NetworkView
from .cms import ContentManagementSystem
from .chromosome import ChromosomeView
from .short_url import ShortAddress
from .pathway import PathwaysView
from .mutation import MutationView


views = [
    GeneView,
    SearchView,
    SequenceView,
    ProteinView,
    NetworkView,
    ContentManagementSystem,
    ChromosomeView,
    ShortAddress,
    PathwaysView,
    MutationView
]
