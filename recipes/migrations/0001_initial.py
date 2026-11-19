"""Mueve Recipe y RecipeIngredient de ``nutrition`` a ``recipes``.

Solo cambia el *estado* de Django: las tablas ``nutrition_recipe`` y
``nutrition_recipeingredient`` se conservan intactas (``Meta.db_table``), por lo
que no hay movimiento de datos. Además se reasignan los ContentType para
conservar permisos y el historial del admin.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def relabel_content_types(apps, schema_editor, old_label, new_label):
    ContentType = apps.get_model("contenttypes", "ContentType")
    for model in ("recipe", "recipeingredient"):
        old = ContentType.objects.filter(app_label=old_label, model=model).first()
        if old is None:
            continue
        if ContentType.objects.filter(app_label=new_label, model=model).exists():
            # Ya existe el destino (p. ej. creado por post_migrate): se deja el
            # original intacto para no perder referencias.
            continue
        old.app_label = new_label
        old.save(update_fields=["app_label"])


def forwards(apps, schema_editor):
    relabel_content_types(apps, schema_editor, "nutrition", "recipes")


def backwards(apps, schema_editor):
    relabel_content_types(apps, schema_editor, "recipes", "nutrition")


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("nutrition", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="Recipe",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("name", models.CharField(max_length=200, verbose_name="Nombre")),
                        ("description", models.TextField(blank=True, verbose_name="Descripción")),
                        ("instructions", models.TextField(blank=True, verbose_name="Preparación")),
                        ("servings", models.PositiveIntegerField(default=1, verbose_name="Raciones")),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name="Usuario")),
                    ],
                    options={
                        "verbose_name": "Receta",
                        "verbose_name_plural": "Recetas",
                        "db_table": "nutrition_recipe",
                        "ordering": ["name"],
                    },
                ),
                migrations.CreateModel(
                    name="RecipeIngredient",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("quantity_g", models.DecimalField(decimal_places=2, max_digits=7, verbose_name="Cantidad (g)")),
                        ("food", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="nutrition.food", verbose_name="Alimento")),
                        ("recipe", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ingredients", to="recipes.recipe")),
                    ],
                    options={
                        "verbose_name": "Ingrediente",
                        "verbose_name_plural": "Ingredientes",
                        "db_table": "nutrition_recipeingredient",
                    },
                ),
            ],
        ),
        migrations.RunPython(forwards, backwards),
    ]
