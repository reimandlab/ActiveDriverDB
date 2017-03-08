from collections import OrderedDict

from flask import render_template as template
from flask_classful import FlaskView
from flask_login import current_user
from models import Protein
from models import Mutation
#from models import Domain
#from models import Site


class MutationView(FlaskView):

    def show(self, refseq, position, alt):

        protein = Protein.query.filter_by(refseq=refseq).first_or_404()

        mutation = Mutation.query.filter_by(
            protein=protein,
            position=int(position),
            alt=alt
        ).one()

        # in case we also want to show also non-confirmed mutations:
        """
        from database import get_or_create

        mutation, _ = get_or_create(
            Mutation,
            protein=protein,
            # setting id directly is easier than forcing update outside session
            protein_id=protein.id,
            position=int(position),
            alt=alt
        )
        """
        datasets = OrderedDict()

        for source, dataset in mutation.sources_dict.items():
            if source != 'user':
                datasets['Mutation.sources:in:' + source] = dataset

        for dataset in current_user.datasets:
            if mutation in dataset.mutations:
                datasets['UserMutations.sources:in:' + dataset.uri] = dataset

        return template(
            'mutation/show.html',
            mutation=mutation,
            protein=protein,
            datasets=datasets
        )

