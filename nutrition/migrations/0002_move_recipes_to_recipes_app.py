"""Elimina Recipe y RecipeIngredient del estado de ``nutrition``.

Solo estado: las tablas pasan a pertenecer a la app ``recipes``
(ver recipes/migrations/0001_initial.py) y NO se borran.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("nutrition", "0001_initial"),
        ("recipes", "0001_initial"),
        ("tracking", "0002_foodlogitem_recipe_to_recipes_app"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(name="RecipeIngredient"),
                migrations.DeleteModel(name="Recipe"),
            ],
        ),
    ]
