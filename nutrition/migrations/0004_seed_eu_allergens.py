"""Puebla los 14 alérgenos de declaración obligatoria (Reglamento UE 1169/2011)."""

from django.db import migrations

EU_ALLERGENS = [
    ("gluten", "Cereales con gluten", "bi-grain"),
    ("crustaceans", "Crustáceos", "bi-water"),
    ("eggs", "Huevos", "bi-egg"),
    ("fish", "Pescado", "bi-tsunami"),
    ("peanuts", "Cacahuetes", "bi-nut"),
    ("soy", "Soja", "bi-flower1"),
    ("milk", "Leche y lácteos", "bi-cup-straw"),
    ("tree-nuts", "Frutos de cáscara", "bi-tree"),
    ("celery", "Apio", "bi-flower2"),
    ("mustard", "Mostaza", "bi-droplet"),
    ("sesame", "Granos de sésamo", "bi-circle-fill"),
    ("sulfites", "Dióxido de azufre y sulfitos", "bi-exclamation-triangle"),
    ("lupin", "Altramuces", "bi-flower3"),
    ("molluscs", "Moluscos", "bi-shell"),
]


def seed_allergens(apps, schema_editor):
    Allergen = apps.get_model("nutrition", "Allergen")
    for code, name, icon in EU_ALLERGENS:
        Allergen.objects.get_or_create(code=code, defaults={"name": name, "icon": icon})


class Migration(migrations.Migration):

    dependencies = [
        ("nutrition", "0003_allergen_food_data_source_food_external_id_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_allergens, reverse_code=migrations.RunPython.noop),
    ]
