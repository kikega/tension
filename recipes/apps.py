from django.apps import AppConfig


class RecipesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "recipes"
    verbose_name = "Recetas"

    def ready(self):
        import recipes.signals  # noqa: F401
