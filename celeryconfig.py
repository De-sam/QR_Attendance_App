from celery import Celery
from celery.schedules import crontab
import os

app = Celery('myapp',
             broker=os.getenv('BROKER_URL', 'redis://red-cpo2mtdds78s73b95tpg:6379/0'),
             backend=os.getenv('RESULT_BACKEND', 'redis://red-cpo2mtdds78s73b95tpg:6379/0'))

app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='UTC',
    enable_utc=True,
    broker_connection_retry_on_startup=True,
)

app.conf.beat_schedule = {
    'auto-clock-out-every-2-minutes': {
        'task': 'myapp.tasks.auto_clock_out',
        'schedule': crontab(minute='*/2'),  # Every 2 minutes
    },
}

