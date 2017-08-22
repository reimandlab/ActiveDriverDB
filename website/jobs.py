from sqlalchemy.exc import SQLAlchemyError

from database import db
from models import UsersMutationsDataset


def hard_delete_expired_datasets():
    removed = 0
    for dataset in UsersMutationsDataset.query.filter_by(is_expired=True):
        dataset.remove(commit=False)
        removed += 1

    try:
        db.session.commit()
        print('Scheduled hard delete job performed successfully, removed %s datasets' % removed)
    except SQLAlchemyError:
        db.session.rollback()
        print('Error: Datasets hard delete commit failed')

    return removed
