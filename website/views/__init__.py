from website.views.gene import GeneView
from website.views.search import SearchView
from website.views.protein import ProteinView
from website.views.network import NetworkView
from website.views.cms import ContentManagmentSystem
from website.views.chromosome import ChromosomeView
from website.views.short_url import ShortAddress
from website.views.pathway import PathwayView


views = [
    GeneView,
    SearchView,
    ProteinView,
    NetworkView,
    ContentManagmentSystem,
    ChromosomeView,
    ShortAddress,
    PathwayView
]
