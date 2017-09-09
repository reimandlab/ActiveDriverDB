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

    def make_association_table(fk1, fk2):
        """Create an association table basing on names of two given foreign keys.

        From keys: `site.id` and `kinase.id` a table named: site_kinase_association
        will be created and it will contain two columns: `site_id` and `kinase_id`.
        """
        table_name = '%s_%s_association' % (fk1.split('.')[0], fk2.split('.')[0])
        return db.Table(
            table_name, db.metadata,
            db.Column(fk1.replace('.', '_'), db.Integer, db.ForeignKey(fk1, ondelete='cascade')),
            db.Column(fk2.replace('.', '_'), db.Integer, db.ForeignKey(fk2, ondelete='cascade')),
            info={'bind_key': bind}
        )
    return make_association_table
