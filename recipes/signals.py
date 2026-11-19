"""Señales para mantener sincronizados los valores nutricionales cacheados de Recipe."""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from nutrition.models import Food

from .models import Recipe, RecipeIngredient, RecipeMedia, RecipeStep
from .services.recipe_nutrition import recalculate_recipe_cache


@receiver([post_save, post_delete], sender=RecipeIngredient)
def sync_recipe_cache_on_ingredient_change(sender, instance, **kwargs):
    if kwargs.get("raw"):
        return
    if instance.recipe_id:
        recipe = Recipe.objects.filter(pk=instance.recipe_id).first()
        if recipe is not None:
            recalculate_recipe_cache(recipe)


@receiver(post_save, sender=Recipe)
def sync_recipe_cache_on_recipe_save(sender, instance, created, **kwargs):
    if kwargs.get("raw") or created:
        return
    # Recalcula si cambian raciones o peso cocinado (update() en recalculate_recipe_cache no re-dispara post_save).
    recalculate_recipe_cache(instance)


@receiver(post_save, sender=Food)
def sync_recipes_cache_on_food_change(sender, instance, created, **kwargs):
    if kwargs.get("raw") or created:
        return
    affected = Recipe.objects.filter(ingredients__food=instance).distinct()
    for recipe in affected:
        recalculate_recipe_cache(recipe)


def _delete_field_file(field_file) -> None:
    if field_file and field_file.name:
        try:
            field_file.storage.delete(field_file.name)
        except Exception:
            pass


@receiver(post_delete, sender=RecipeMedia)
def cleanup_recipe_media_files(sender, instance, **kwargs):
    _delete_field_file(instance.image)
    _delete_field_file(instance.image_medium)
    _delete_field_file(instance.image_thumb)


@receiver(post_delete, sender=RecipeStep)
def cleanup_recipe_step_files(sender, instance, **kwargs):
    _delete_field_file(instance.image)
    _delete_field_file(instance.image_thumb)
