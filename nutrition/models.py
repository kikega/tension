from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings


class FoodCategory(models.Model):
    """Categoría de alimento (Verduras, Lácteos, Carnes, etc.)."""

    name = models.CharField(max_length=100, unique=True, verbose_name=_("Nombre"))
    description = models.TextField(blank=True, verbose_name=_("Descripción"))

    class Meta:
        ordering = ["name"]
        verbose_name = _("Categoría")
        verbose_name_plural = _("Categorías")

    def __str__(self) -> str:
        return self.name


class Allergen(models.Model):
    """Alérgenos de declaración obligatoria (Reglamento UE 1169/2011)."""

    code = models.SlugField(max_length=40, unique=True, verbose_name=_("Código"))
    name = models.CharField(max_length=100, unique=True, verbose_name=_("Nombre"))
    icon = models.CharField(max_length=40, blank=True, verbose_name=_("Icono"))

    class Meta:
        ordering = ["name"]
        verbose_name = _("Alérgeno")
        verbose_name_plural = _("Alérgenos")

    def __str__(self) -> str:
        return self.name


class Food(models.Model):
    """Alimento con su composición nutricional completa."""

    SEASON_CHOICES = [
        ("all", "Todo el año"),
        ("spring", "Primavera"),
        ("summer", "Verano"),
        ("autumn", "Otoño"),
        ("winter", "Invierno"),
    ]

    SOURCE_CHOICES = [
        ("manual", "Manual"),
        ("bedca", "BEDCA"),
        ("openfoodfacts", "Open Food Facts"),
        ("other", "Otra"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_("Usuario")
    )
    category = models.ForeignKey(FoodCategory, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Categoría"))
    name = models.CharField(max_length=200, verbose_name=_("Alimento"))
    description = models.TextField(blank=True, verbose_name=_("Descripción"))
    seasonality = models.CharField(max_length=10, choices=SEASON_CHOICES, default="all", verbose_name=_("Estacionalidad"))
    edible_portion = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name=_("Porción comestible (%)"))
    nutritional_rating = models.CharField(max_length=100, blank=True, verbose_name=_("Valoración nutricional"))
    allergens = models.ManyToManyField(Allergen, blank=True, related_name="foods", verbose_name=_("Alérgenos"))
    data_source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="manual", verbose_name=_("Fuente de datos"))
    external_id = models.CharField(max_length=64, blank=True, db_index=True, verbose_name=_("ID externo"))

    # Composición nutricional por 100 g (todos opcionales)
    energy_kcal = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name=_("Energía (kcal)"))
    proteins_g = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Proteínas (g)"))
    lipids_g = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Lípidos totales (g)"))
    cholesterol_mg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Colesterol (mg/1000kcal)"))
    carbohydrates_g = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Hidratos de carbono (g)"))
    fiber_g = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Fibra (g)"))
    water_g = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Agua (g)"))
    calcium_mg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Calcio (mg)"))
    iron_mg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Hierro (mg)"))
    iodine_ug = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Yodo (µg)"))
    magnesium_mg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Magnesio (mg)"))
    zinc_mg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Zinc (mg)"))
    sodium_mg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Sodio (mg)"))
    potassium_mg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Potasio (mg)"))
    phosphorus_mg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Fósforo (mg)"))
    selenium_ug = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Selenio (µg)"))
    thiamine_mg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Tiamina (mg)"))
    riboflavin_mg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Riboflavina (mg)"))
    vitamin_b6_mg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Vitamina B6 (mg)"))
    folate_ug = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Folatos (µg)"))
    vitamin_b12_ug = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Vitamina B12 (µg)"))
    vitamin_c_mg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Vitamina C (mg)"))
    vitamin_a_ug = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Vitamina A (µg)"))
    vitamin_d_ug = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Vitamina D (µg)"))
    vitamin_e_mg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Vitamina E (mg)"))
    glycemic_index = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name=_("Índice glucémico"))

    class Meta:
        ordering = ["name"]
        verbose_name = _("Alimento")
        verbose_name_plural = _("Alimentos")

    def __str__(self) -> str:
        return self.name


class HouseholdMeasure(models.Model):
    """Medida casera de un alimento y su equivalencia en gramos (ej. '1 huevo M' = 53 g)."""

    food = models.ForeignKey(Food, related_name="household_measures", on_delete=models.CASCADE, verbose_name=_("Alimento"))
    name = models.CharField(max_length=100, verbose_name=_("Medida casera"))
    grams = models.DecimalField(max_digits=7, decimal_places=2, verbose_name=_("Equivalencia (g)"))

    class Meta:
        ordering = ["food__name", "name"]
        unique_together = ("food", "name")
        verbose_name = _("Medida casera")
        verbose_name_plural = _("Medidas caseras")

    def __str__(self) -> str:
        return f"{self.food.name}: {self.name} ({self.grams} g)"


class NutritionalReference(models.Model):
    """Valores diarios recomendados de referencia nutricional por género."""

    GENDER_CHOICES = [("male", "Hombre"), ("female", "Mujer")]

    gender = models.CharField(max_length=6, choices=GENDER_CHOICES, unique=True, verbose_name=_("Género"))
    energy_kcal = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name=_("Energía (kcal)"))
    proteins_g = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Proteínas (g)"))
    lipids_g = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Lípidos (g)"))
    cholesterol_mg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Colesterol (mg/1000kcal)"))
    carbohydrates_g = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Hidratos de carbono (g)"))
    fiber_g = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Fibra (g)"))
    calcium_mg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Calcio (mg)"))
    iron_mg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Hierro (mg)"))
    iodine_ug = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Yodo (µg)"))
    magnesium_mg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Magnesio (mg)"))
    zinc_mg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Zinc (mg)"))
    sodium_mg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Sodio (mg)"))
    potassium_mg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Potasio (mg)"))
    phosphorus_mg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Fósforo (mg)"))
    selenium_ug = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Selenio (µg)"))
    thiamine_mg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Tiamina (mg)"))
    riboflavin_mg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Riboflavina (mg)"))
    vitamin_b6_mg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Vitamina B6 (mg)"))
    folate_ug = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Folatos (µg)"))
    vitamin_b12_ug = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Vitamina B12 (µg)"))
    vitamin_c_mg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Vitamina C (mg)"))
    vitamin_a_ug = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Vitamina A (µg)"))
    vitamin_d_ug = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Vitamina D (µg)"))
    vitamin_e_mg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Vitamina E (mg)"))

    class Meta:
        verbose_name = _("Referencia Nutricional")
        verbose_name_plural = _("Referencias Nutricionales")

    def __str__(self) -> str:
        return f"Referencia {self.get_gender_display()}"
