"""FoodLogItem.recipe apunta ahora a recipes.Recipe.

Solo estado: la tabla destino (nutrition_recipe) no cambia, así que la
restricción FK existente en la base de datos sigue siendo válida.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("recipes", "0001_initial"),
        ("tracking", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name="foodlogitem",
                    name="recipe",
                    field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="recipes.recipe", verbose_name="Receta"),
                ),
            ],
        ),
    ]
