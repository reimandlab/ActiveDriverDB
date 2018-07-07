"""Adapted from flask.pocoo.org/docs/0.12/patterns/celery/ Flask documentation,
therefore Flask documentation, BSD licence conditions may apply."""
import celery


class Celery(celery.Celery):

    def init_app(self, app):
        self.__init__(app)

    def __init__(self, app=None):
        if app:
            super().__init__(
                app.import_name,
                backend=app.config['CELERY_RESULT_BACKEND'],
                broker=app.config['CELERY_BROKER_URL']
            )
            self.conf.update(app.config)

            TaskBase = self.Task

            class ContextTask(TaskBase):
                abstract = True

                def __call__(self, *args, **kwargs):
                    with app.app_context():
                        return TaskBase.__call__(self, *args, **kwargs)

            self.Task = ContextTask
        else:
            super().__init__()
