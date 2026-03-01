from django.db import models
from django.utils.translation import gettext_lazy as _


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


class Food(models.Model):
    """Alimento con su composición nutricional completa."""

    SEASON_CHOICES = [
        ("all", "Todo el año"),
        ("spring", "Primavera"),
        ("summer", "Verano"),
        ("autumn", "Otoño"),
        ("winter", "Invierno"),
    ]

    category = models.ForeignKey(FoodCategory, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Categoría"))
    name = models.CharField(max_length=200, verbose_name=_("Alimento"))
    description = models.TextField(blank=True, verbose_name=_("Descripción"))
    seasonality = models.CharField(max_length=10, choices=SEASON_CHOICES, default="all", verbose_name=_("Estacionalidad"))
    edible_portion = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name=_("Porción comestible (%)"))
    nutritional_rating = models.CharField(max_length=100, blank=True, verbose_name=_("Valoración nutricional"))

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

    class Meta:
        ordering = ["name"]
        verbose_name = _("Alimento")
        verbose_name_plural = _("Alimentos")

    def __str__(self) -> str:
        return self.name


class NutritionalReference(models.Model):
    """Valores diarios recomendados de referencia nutricional por género."""

    GENDER_CHOICES = [("male", "Hombre"), ("female", "Mujer")]

    gender = models.CharField(max_length=6, choices=GENDER_CHOICES, unique=True, verbose_name=_("Género"))
    energy_kcal = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name=_("Energía (kcal)"))
    proteins_g = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Proteínas (g)"))
    lipids_g = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Lípidos (g)"))
    carbohydrates_g = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Hidratos de carbono (g)"))
    fiber_g = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Fibra (g)"))
    calcium_mg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Calcio (mg)"))
    iron_mg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Hierro (mg)"))
    vitamin_c_mg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Vitamina C (mg)"))
    vitamin_d_ug = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Vitamina D (µg)"))

    class Meta:
        verbose_name = _("Referencia Nutricional")
        verbose_name_plural = _("Referencias Nutricionales")

    def __str__(self) -> str:
        return f"Referencia {self.get_gender_display()}"


class Recipe(models.Model):
    """Receta de cocina con cálculo nutricional basado en ingredientes."""

    name = models.CharField(max_length=200, verbose_name=_("Nombre"))
    description = models.TextField(blank=True, verbose_name=_("Descripción"))
    instructions = models.TextField(blank=True, verbose_name=_("Preparación"))
    servings = models.PositiveIntegerField(default=1, verbose_name=_("Raciones"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("Receta")
        verbose_name_plural = _("Recetas")

    def __str__(self) -> str:
        return self.name

    def calculate_nutrition(self) -> dict:
        """Calcula la composición nutricional total de la receta en base a sus ingredientes."""
        NUTRIENT_FIELDS = [
            "energy_kcal", "proteins_g", "lipids_g", "cholesterol_mg",
            "carbohydrates_g", "fiber_g", "water_g", "calcium_mg", "iron_mg",
            "iodine_ug", "magnesium_mg", "zinc_mg", "sodium_mg", "potassium_mg",
            "phosphorus_mg", "selenium_ug", "thiamine_mg", "riboflavin_mg",
            "vitamin_b6_mg", "folate_ug", "vitamin_b12_ug", "vitamin_c_mg",
            "vitamin_a_ug", "vitamin_d_ug", "vitamin_e_mg",
        ]
        totals: dict = {field: 0 for field in NUTRIENT_FIELDS}
        for ingredient in self.ingredients.select_related("food").all():
            factor = float(ingredient.quantity_g) / 100.0
            for field in NUTRIENT_FIELDS:
                value = getattr(ingredient.food, field)
                if value is not None:
                    totals[field] += float(value) * factor
        return totals


class RecipeIngredient(models.Model):
    """Ingrediente de una receta con cantidad en gramos."""

    recipe = models.ForeignKey(Recipe, related_name="ingredients", on_delete=models.CASCADE)
    food = models.ForeignKey(Food, on_delete=models.CASCADE, verbose_name=_("Alimento"))
    quantity_g = models.DecimalField(max_digits=7, decimal_places=2, verbose_name=_("Cantidad (g)"))

    class Meta:
        verbose_name = _("Ingrediente")
        verbose_name_plural = _("Ingredientes")

    def __str__(self) -> str:
        return f"{self.food.name} — {self.quantity_g}g"
