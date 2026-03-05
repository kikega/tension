from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool("DEBUG", default=True)

# Add development-only apps
INSTALLED_APPS += [
    "django_extensions",
]
