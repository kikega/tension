from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool("DEBUG", default=False)

# Configuration for PostgreSQL in production (requires DATABASE_URL in .env)
DATABASES = {
    "default": env.db("DATABASE_URL")
}

# Logging configuration for Production
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "db_file": {
            "level": "WARNING",
            "class": "logging.FileHandler",
            "filename": LOGS_DIR / "db_transactions.log",
            "formatter": "verbose",
        },
        "auth_file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": LOGS_DIR / "auth.log",
            "formatter": "verbose",
        },
        'file_errors': {
            'level': 'ERROR',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': LOGS_DIR / "errors.log",
            'when': 'midnight',
            'backupCount': 30,
            'utc': True,
            'formatter': 'verbose',
        },
    },
    "loggers": {
        "django.db.backends": {
            "handlers": ["console", "db_file"],
            "level": "WARNING",
            "propagate": False,
        },
        "accounts": {  # Custom logger for authentication events if needed
            "handlers": ["console", "auth_file"],
            "level": "INFO",
            "propagate": False,
        },
        # We can also log general django security requests
        "django.security": {
            "handlers": ["console", "auth_file"],
            "level": "INFO",
            "propagate": False,
        },
        # Errores generales de Django (captura los 500)
        'django.request': {
            'handlers': ['file_errors'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}
