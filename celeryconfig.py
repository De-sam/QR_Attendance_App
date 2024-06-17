from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'auto-clock-out-every-5-minutes': {
        'task': 'myapp.tasks.auto_clock_out',
        'schedule': crontab(minute='*/5'),  # Every 30 minutes
    },
}

broker_url = 'redis://localhost:6379/0'
result_backend = 'redis://localhost:6379/0'
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']
timezone = 'UTC'
enable_utc = True
broker_connection_retry_on_startup = True
