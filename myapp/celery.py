from celery import Celery

def make_celery(app=None):
    celery = Celery(
        'myapp',
        backend=app.config['CELERY_RESULT_BACKEND'] if app else None,
        broker=app.config['CELERY_BROKER_URL'] if app else None
    )
    if app:
        celery.conf.update(app.config)
        celery.config_from_object('celeryconfig')

        class ContextTask(celery.Task):
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)
        celery.Task = ContextTask
    
    # Autodiscover tasks from the 'myapp' package
    celery.autodiscover_tasks(['myapp'])
    
    return celery

celery = make_celery()
