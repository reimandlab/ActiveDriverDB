from .protein_data import *
from .mutations import MutationImportManager
from flask import current_app


def import_all():
    muts_import_manager = MutationImportManager()
    global genes
    genes, proteins = create_proteins_and_genes()
    load_sequences(proteins)
    select_preferred_isoforms(genes)
    load_disorder(proteins)
    load_domains(proteins)
    load_domains_hierarchy()
    load_domains_types()
    load_cancers()
    global kinase_protein_mappings
    kinase_protein_mappings = load_kinase_mappings()
    kinases, groups = load_sites(proteins)
    kinases, groups = load_kinase_classification(kinases, groups)
    load_pathways(genes)
    print('Adding kinases to the session...')
    db.session.add_all(kinases.values())
    print('Adding groups to the session...')
    db.session.add_all(groups.values())
    del kinases
    del groups
    remove_wrong_proteins(proteins)
    calculate_interactors(proteins)
    db.session.commit()
    with current_app.app_context():
        muts_import_manager.perform('load', proteins)
    for importer in IMPORTERS:
        results = importer()
        db.session.add_all(results)
        db.session.commit()
