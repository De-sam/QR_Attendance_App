from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'auto-clock-out-every-2-minutes': {
        'task': 'myapp.tasks.auto_clock_out',
        'schedule': crontab(minute='*/2'),  # Every 2 minutes
    },
}

broker_url = 'redis://red-cpo2mtdds78s73b95tpg:6379'
result_backend = 'redis://red-cpo2mtdds78s73b95tpg:6379'
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']
timezone = 'UTC'
enable_utc = True
broker_connection_retry_on_startup = True
