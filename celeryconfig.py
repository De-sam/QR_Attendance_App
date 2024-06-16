from celery.schedules import crontab

CELERYBEAT_SCHEDULE = {
    'auto-clock-out-every-30-minutes': {
        'task': 'your_flask_app.tasks.auto_clock_out',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
    },
}

CELERY_TIMEZONE = 'UTC'
