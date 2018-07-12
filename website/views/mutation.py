from flask import render_template as template
from flask_classful import FlaskView
from flask_login import current_user
from models import Protein
from models import Mutation


class MutationView(FlaskView):

    def show(self, refseq, position, alt):

        protein = Protein.query.filter_by(refseq=refseq).first_or_404()

        mutation = Mutation.query.filter_by(
            protein=protein,
            position=int(position),
            alt=alt
        ).first_or_404()

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
        datasets = []

        sources_with_mutation = mutation.sources_dict

        for source in mutation.source_fields:
            model = mutation.get_source_model(source)
            datasets.append({
                'filter': 'Mutation.sources:in:' + source,
                'name': model.display_name,
                'mutation_present': sources_with_mutation.get(source, False)
            })

        user_datasets = []

        for dataset in current_user.datasets:
            if mutation in dataset.mutations:
                datasets.append({
                    'filter': 'UserMutations.sources:in:' + dataset.uri,
                    'name': dataset.name,
                    'mutation_present': True
                })
                user_datasets.append(dataset)

        return template(
            'mutation/show.html',
            mutation=mutation,
            protein=protein,
            datasets=datasets,
            user_datasets=user_datasets
        )

