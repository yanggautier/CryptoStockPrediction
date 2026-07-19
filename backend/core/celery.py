import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

app = Celery("core")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {

    # Collecte données : chaque nuit à 1h00
    "collect-data-daily": {
        "task":     "predictions.tasks.collect_data_task",
        "schedule": crontab(hour=1, minute=0),
    },

    # Rapport MLOps + auto-retrain : chaque matin à 6h00
    "mlops-daily-report": {
        "task":     "predictions.tasks.mlops_report_task",
        "schedule": crontab(hour=6, minute=0),
    },

    # Collecte news sentiment : toutes les 6h
    "news-sentiment": {
        "task":     "predictions.tasks.collect_news_task",
        "schedule": crontab(hour="0,6,12,18", minute=30),
    },

    # Mise à jour leaderboard : toutes les heures
    "leaderboard-update": {
        "task":     "predictions.tasks.update_leaderboard_task",
        "schedule": crontab(minute=0),
    },

    # Mise à jour prix positions : toutes les 15 min
    "prices-update": {
        "task":     "predictions.tasks.update_prices_task",
        "schedule": crontab(minute="*/15"),
    },
}

app.conf.timezone = "Europe/Paris"