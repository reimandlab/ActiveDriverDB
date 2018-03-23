import operator
from functools import reduce

from database import db


def generic_aggregator(attribute, flatten=False, is_callable=False):

    def aggregator(self, data_filter=lambda x: x):
        data = data_filter(self.data)
        aggregated = [
            getattr(datum, attribute)(data_filter) if is_callable else getattr(datum, attribute)
            for datum in data
        ]
        if aggregated and flatten:
            return reduce(operator.add, aggregated)
        else:
            return aggregated

    return aggregator


def association_table_super_factory(bind=None):

    def make_association_table(fk1, fk2, index=False):
        """Create an association table basing on names of two given foreign keys.

        From keys: `site.id` and `kinase.id` a table named: site_kinase_association
        will be created and it will contain two columns: `site_id` and `kinase_id`.

        The foreign keys can be provided as models properties, e.g. Model.id,
        or as SQL strings, e.g. 'model.id'.
        """
        if not isinstance(fk1, str):
            fk1 = f'{fk1.table}.{fk1.name}'
        if not isinstance(fk2, str):
            fk2 = f'{fk2.table}.{fk2.name}'

        fk1_table = fk1.split('.')[0]
        fk2_table = fk2.split('.')[0]

        table_name = f'{fk1_table}_{fk2_table}_association'

        col1 = fk1.replace('.', '_')
        col2 = fk2.replace('.', '_')

        table_args = [
            table_name,
            db.metadata,
            db.Column(col1, db.Integer, db.ForeignKey(fk1, ondelete='cascade')),
            db.Column(col2, db.Integer, db.ForeignKey(fk2, ondelete='cascade')),
        ]

        if index:
            table_args.append(
                db.Index(f'idx_{col1}_{col2}', col1, col2)
            )

        return db.Table(
            *table_args,
            info={'bind_key': bind}
        )
    return make_association_table
