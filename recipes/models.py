"""Modelos de recetas (servidos en recetas.egalvez.es).

Fase 1: movidos desde ``nutrition`` conservando las tablas ``nutrition_recipe``
y ``nutrition_recipeingredient`` mediante ``Meta.db_table``.
Fase 2: enriquecidos con taxonomía, pasos estructurados, grupos de ingredientes,
medidas caseras, rendimiento de cocción, vídeo de YouTube y caché nutricional.
"""

from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from nutrition.models import Allergen, Food, HouseholdMeasure
from nutrition.services.nutrition_calculator import NUTRIENT_FIELDS

from .services.media_processor import (
    STEP_VARIANT_WIDTHS,
    VARIANT_WIDTHS,
    process_image_variants,
    validate_uploaded_image,
)
from .validators import extract_youtube_id, validate_youtube_url


def recipe_media_upload_to(instance, filename: str) -> str:
    recipe_id = instance.recipe_id or "tmp"
    return f"recipes/{recipe_id}/gallery/{filename}"


def recipe_step_upload_to(instance, filename: str) -> str:
    recipe_id = instance.recipe_id or "tmp"
    return f"recipes/{recipe_id}/steps/{filename}"


class RecipeCategory(models.Model):
    """Clasificación principal de recetas (tipo de plato o momento de comida)."""

    KIND_CHOICES = [
        ("dish_type", "Tipo de plato"),
        ("meal_type", "Momento del día"),
    ]

    slug = models.SlugField(max_length=80, unique=True, verbose_name=_("Slug"))
    name = models.CharField(max_length=100, verbose_name=_("Nombre"))
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="dish_type", db_index=True, verbose_name=_("Tipo"))
    order = models.PositiveSmallIntegerField(default=0, verbose_name=_("Orden"))

    class Meta:
        ordering = ["kind", "order", "name"]
        verbose_name = _("Categoría de receta")
        verbose_name_plural = _("Categorías de recetas")

    def __str__(self) -> str:
        return f"{self.name} ({self.get_kind_display()})"


class RecipeTag(models.Model):
    """Etiquetas transversales: dieta, técnica de cocción, cocina o general."""

    KIND_CHOICES = [
        ("diet", "Dieta"),
        ("technique", "Técnica"),
        ("cuisine", "Cocina"),
        ("general", "General"),
    ]

    slug = models.SlugField(max_length=80, unique=True, verbose_name=_("Slug"))
    name = models.CharField(max_length=100, verbose_name=_("Nombre"))
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="general", db_index=True, verbose_name=_("Tipo"))

    class Meta:
        ordering = ["kind", "name"]
        verbose_name = _("Etiqueta")
        verbose_name_plural = _("Etiquetas")

    def __str__(self) -> str:
        return self.name


class Utensil(models.Model):
    """Utensilio o electrodoméstico necesario para preparar una receta."""

    slug = models.SlugField(max_length=80, unique=True, verbose_name=_("Slug"))
    name = models.CharField(max_length=100, unique=True, verbose_name=_("Nombre"))

    class Meta:
        ordering = ["name"]
        verbose_name = _("Utensilio")
        verbose_name_plural = _("Utensilios")

    def __str__(self) -> str:
        return self.name


class RecipeQuerySet(models.QuerySet):
    def visible_for(self, user):
        """Recetas visibles para ``user``: todas las publicadas + las propias (o todas si staff)."""
        if user is None or not user.is_authenticated:
            return self.none()
        if user.is_staff:
            return self
        return self.filter(Q(status=Recipe.STATUS_PUBLISHED) | Q(user=user))

    def editable_by(self, user):
        """Recetas que ``user`` puede modificar o eliminar (solo propias o staff)."""
        if user is None or not user.is_authenticated:
            return self.none()
        if user.is_staff:
            return self
        return self.filter(user=user)


class Recipe(models.Model):
    """Receta de cocina con cálculo nutricional basado en ingredientes."""

    STATUS_DRAFT = "draft"
    STATUS_PUBLISHED = "published"
    STATUS_PRIVATE = "private"
    STATUS_CHOICES = [
        (STATUS_PUBLISHED, "Publicada"),
        (STATUS_DRAFT, "Borrador"),
        (STATUS_PRIVATE, "Privada"),
    ]

    DIFFICULTY_CHOICES = [
        ("easy", "Fácil"),
        ("medium", "Media"),
        ("hard", "Difícil"),
    ]

    COST_CHOICES = [
        ("low", "Económica"),
        ("medium", "Media"),
        ("high", "Alta"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_("Usuario"),
    )
    name = models.CharField(max_length=200, verbose_name=_("Nombre"))
    slug = models.SlugField(max_length=220, unique=True, blank=True, verbose_name=_("Slug"))
    description = models.TextField(blank=True, verbose_name=_("Descripción"))
    instructions = models.TextField(blank=True, verbose_name=_("Preparación"))
    servings = models.PositiveIntegerField(default=1, verbose_name=_("Raciones"))

    # Estado editorial y metadatos culinarios
    status = models.CharField(
        max_length=12,
        choices=STATUS_CHOICES,
        default=STATUS_PUBLISHED,
        db_index=True,
        verbose_name=_("Estado"),
    )
    prep_time_min = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Tiempo de preparación (min)"))
    cook_time_min = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Tiempo de cocción (min)"))
    rest_time_min = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Tiempo de reposo (min)"))
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default="medium", verbose_name=_("Dificultad"))
    cost_level = models.CharField(max_length=10, choices=COST_CHOICES, blank=True, verbose_name=_("Coste aproximado"))
    seasonality = models.CharField(max_length=10, choices=Food.SEASON_CHOICES, default="all", verbose_name=_("Temporada"))
    cooked_weight_g = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Peso final cocinado (g)"),
        help_text=_("Opcional. Si se indica, los valores por 100 g de plato terminado usan este peso."),
    )
    video_url = models.URLField(
        blank=True,
        validators=[validate_youtube_url],
        verbose_name=_("Vídeo de YouTube"),
        help_text=_("URL de YouTube (se abrirá incrustado en un popup)."),
    )

    # Taxonomía
    categories = models.ManyToManyField(RecipeCategory, blank=True, related_name="recipes", verbose_name=_("Categorías"))
    tags = models.ManyToManyField(RecipeTag, blank=True, related_name="recipes", verbose_name=_("Etiquetas"))
    utensils = models.ManyToManyField(Utensil, blank=True, related_name="recipes", verbose_name=_("Utensilios"))

    # Campos nutricionales cacheados (actualizados automáticamente por señales)
    cached_total_weight_g = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    cached_kcal_per_serving = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"), db_index=True)
    cached_proteins_per_serving = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0.00"), db_index=True)
    cached_carbs_per_serving = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0.00"))
    cached_lipids_per_serving = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0.00"))
    cached_fiber_per_serving = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0.00"))
    cached_sodium_mg_per_serving = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"), db_index=True)
    cached_potassium_mg_per_serving = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    cached_glycemic_load_per_serving = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0.00"))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = RecipeQuerySet.as_manager()

    class Meta:
        db_table = "nutrition_recipe"
        ordering = ["name"]
        verbose_name = _("Receta")
        verbose_name_plural = _("Recetas")

    def __str__(self) -> str:
        return self.name

    def _generate_unique_slug(self) -> str:
        base = slugify(self.name)[:200] or "receta"
        candidate = base
        counter = 2
        qs = Recipe.objects.exclude(pk=self.pk)
        while qs.filter(slug=candidate).exists():
            suffix = f"-{counter}"
            candidate = f"{base[:220 - len(suffix)]}{suffix}"
            counter += 1
        return candidate

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._generate_unique_slug()
        super().save(*args, **kwargs)

    @property
    def total_time_min(self) -> Optional[int]:
        parts = [t for t in (self.prep_time_min, self.cook_time_min, self.rest_time_min) if t is not None]
        return sum(parts) if parts else None

    @property
    def youtube_video_id(self) -> Optional[str]:
        return extract_youtube_id(self.video_url)

    @property
    def youtube_embed_url(self) -> Optional[str]:
        vid = self.youtube_video_id
        return f"https://www.youtube-nocookie.com/embed/{vid}?rel=0" if vid else None

    @property
    def is_dash_friendly(self) -> bool:
        """Indicador orientativo DASH: <= 500 mg de sodio por ración."""
        return float(self.cached_sodium_mg_per_serving) <= 500.0

    @property
    def sodium_potassium_ratio(self) -> Optional[float]:
        """Relación sodio/potasio por ración (ideal < 0.5-1.0 para control de tensión)."""
        k = float(self.cached_potassium_mg_per_serving)
        if k <= 0:
            return None
        return round(float(self.cached_sodium_mg_per_serving) / k, 2)

    def get_allergens(self):
        """Alérgenos presentes en la receta derivados automáticamente de sus ingredientes."""
        return Allergen.objects.filter(foods__recipeingredient__recipe=self).distinct().order_by("name")

    @property
    def cover_media(self):
        """Foto principal de la receta (la marcada como portada o la primera por orden)."""
        media_items = list(self.media.all())
        if not media_items:
            return None
        for item in media_items:
            if item.is_cover:
                return item
        return media_items[0]

    @property
    def gallery_media(self):
        """Todas las fotos de la receta con la portada en primer lugar."""
        return self.media.all().order_by("-is_cover", "order", "id")

    def calculate_total_weight(self) -> float:
        """Suma total del peso (g) de todos los ingredientes de la receta."""
        return sum((float(i.quantity_g) for i in self.ingredients.all()), 0.0)

    def get_effective_weight_g(self) -> float:
        """Peso de referencia para valores por 100 g: cocinado si existe, o suma de ingredientes."""
        if self.cooked_weight_g is not None and float(self.cooked_weight_g) > 0:
            return float(self.cooked_weight_g)
        return self.calculate_total_weight()

    @staticmethod
    def _edible_weight_factor(quantity_g, edible_portion) -> float:
        """Factor de peso comestible sobre 100 g (aplica porción comestible si existe)."""
        edible_ratio = 1.0
        if edible_portion is not None:
            edible_ratio = max(0.0, min(100.0, float(edible_portion))) / 100.0
        return (float(quantity_g) / 100.0) * edible_ratio

    def calculate_nutrition(self) -> dict:
        """Calcula la composición nutricional total de la receta en base a sus ingredientes.

        - Aplica ``edible_portion`` (porción comestible %) cuando está definida en el alimento.
        - ``cholesterol_mg`` está almacenado en mg/1000 kcal, por lo que se convierte
          a mg reales multiplicando por las kcal aportadas por ese ingrediente / 1000.
        """
        totals: dict = {field: 0.0 for field in NUTRIENT_FIELDS}
        for ingredient in self.ingredients.select_related("food").all():
            food = ingredient.food
            factor = self._edible_weight_factor(ingredient.quantity_g, food.edible_portion)
            portion_kcal = float(food.energy_kcal) * factor if food.energy_kcal is not None else 0.0
            for field in NUTRIENT_FIELDS:
                value = getattr(food, field)
                if value is None:
                    continue
                if field == "cholesterol_mg":
                    totals[field] += float(value) * portion_kcal / 1000.0
                else:
                    totals[field] += float(value) * factor
        return totals

    def calculate_glycemic_load(self) -> dict:
        """
        Calcula la carga glucémica (CG) total de la receta en base a sus ingredientes.
        Retorna un diccionario con:
          - 'total_cg': la suma de las CG de los ingredientes
          - 'has_missing_ig': indica si algún ingrediente con carbohidratos carece de IG
        """
        total_cg = 0.0
        has_missing_ig = False
        for ingredient in self.ingredients.select_related("food").all():
            food = ingredient.food
            carbs = float(food.carbohydrates_g or 0)
            if carbs > 0:
                if food.glycemic_index is not None:
                    factor = self._edible_weight_factor(ingredient.quantity_g, food.edible_portion)
                    portion_carbs = carbs * factor
                    total_cg += (float(food.glycemic_index) * portion_carbs) / 100.0
                else:
                    has_missing_ig = True
        return {
            "total_cg": round(total_cg, 2),
            "has_missing_ig": has_missing_ig,
        }


class IngredientGroup(models.Model):
    """Agrupación opcional de ingredientes (ej. 'Para la masa', 'Para la salsa')."""

    recipe = models.ForeignKey(Recipe, related_name="ingredient_groups", on_delete=models.CASCADE, verbose_name=_("Receta"))
    name = models.CharField(max_length=120, verbose_name=_("Nombre del grupo"))
    order = models.PositiveSmallIntegerField(default=0, verbose_name=_("Orden"))

    class Meta:
        ordering = ["order", "id"]
        verbose_name = _("Grupo de ingredientes")
        verbose_name_plural = _("Grupos de ingredientes")

    def __str__(self) -> str:
        return f"{self.recipe.name} — {self.name}"


class RecipeIngredient(models.Model):
    """Ingrediente de una receta con cantidad en gramos y medida casera opcional."""

    recipe = models.ForeignKey(Recipe, related_name="ingredients", on_delete=models.CASCADE)
    group = models.ForeignKey(
        IngredientGroup,
        related_name="ingredients",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Grupo"),
    )
    food = models.ForeignKey(Food, on_delete=models.CASCADE, verbose_name=_("Alimento"))
    quantity_g = models.DecimalField(max_digits=7, decimal_places=2, verbose_name=_("Cantidad (g)"))
    household_measure = models.ForeignKey(
        HouseholdMeasure,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Medida casera"),
    )
    household_quantity = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Cantidad casera"),
    )
    notes = models.CharField(max_length=120, blank=True, verbose_name=_("Nota"))
    order = models.PositiveSmallIntegerField(default=0, verbose_name=_("Orden"))

    class Meta:
        db_table = "nutrition_recipeingredient"
        ordering = ["order", "id"]
        verbose_name = _("Ingrediente")
        verbose_name_plural = _("Ingredientes")

    def save(self, *args, **kwargs):
        # Si se indica medida casera y cantidad pero no quantity_g, se calcula automáticamente.
        if (self.quantity_g is None or self.quantity_g <= 0) and self.household_measure and self.household_quantity:
            self.quantity_g = (Decimal(self.household_quantity) * Decimal(self.household_measure.grams)).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)

    @property
    def display_quantity(self) -> str:
        """Texto amigable: '2 huevo M (106 g)' si hay medida casera, o '106 g'."""
        grams_str = f"{self.quantity_g.normalize():f}" if isinstance(self.quantity_g, Decimal) else f"{self.quantity_g:g}"
        if self.household_measure and self.household_quantity is not None:
            qty_str = f"{self.household_quantity.normalize():f}" if isinstance(self.household_quantity, Decimal) else f"{self.household_quantity:g}"
            return f"{qty_str} {self.household_measure.name} ({grams_str} g)"
        return f"{grams_str} g"

    def __str__(self) -> str:
        return f"{self.food.name} — {self.display_quantity}"


class RecipeStep(models.Model):
    """Paso estructurado de preparación con foto, consejo y temporizador opcionales."""

    recipe = models.ForeignKey(Recipe, related_name="steps", on_delete=models.CASCADE, verbose_name=_("Receta"))
    order = models.PositiveSmallIntegerField(default=1, verbose_name=_("Paso"))
    instruction = models.TextField(verbose_name=_("Instrucción"))
    tip = models.CharField(max_length=255, blank=True, verbose_name=_("Consejo"))
    timer_seconds = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Temporizador (segundos)"))
    image = models.ImageField(
        upload_to=recipe_step_upload_to,
        blank=True,
        null=True,
        validators=[validate_uploaded_image],
        verbose_name=_("Foto del paso"),
    )
    image_thumb = models.ImageField(upload_to=recipe_step_upload_to, blank=True, editable=False)
    image_alt = models.CharField(max_length=200, blank=True, verbose_name=_("Texto alternativo"))

    class Meta:
        ordering = ["order", "id"]
        verbose_name = _("Paso de receta")
        verbose_name_plural = _("Pasos de receta")

    def save(self, *args, **kwargs):
        if self.image and not getattr(self.image, "_committed", True):
            variants, _size = process_image_variants(self.image, widths=STEP_VARIANT_WIDTHS)
            self.image.save(variants["large"].name, variants["large"], save=False)
            self.image_thumb.save(variants["thumb"].name, variants["thumb"], save=False)
        super().save(*args, **kwargs)

    @property
    def timer_minutes(self) -> Optional[float]:
        if not self.timer_seconds:
            return None
        return round(self.timer_seconds / 60.0, 1)

    def __str__(self) -> str:
        return f"{self.recipe.name} — Paso {self.order}"


class RecipeMedia(models.Model):
    """Fotografía de portada o galería de una receta con variantes WebP responsivas."""

    recipe = models.ForeignKey(Recipe, related_name="media", on_delete=models.CASCADE, verbose_name=_("Receta"))
    image = models.ImageField(
        upload_to=recipe_media_upload_to,
        validators=[validate_uploaded_image],
        verbose_name=_("Imagen"),
    )
    image_medium = models.ImageField(upload_to=recipe_media_upload_to, blank=True, editable=False)
    image_thumb = models.ImageField(upload_to=recipe_media_upload_to, blank=True, editable=False)
    width = models.PositiveIntegerField(null=True, blank=True, editable=False)
    height = models.PositiveIntegerField(null=True, blank=True, editable=False)
    alt_text = models.CharField(max_length=200, blank=True, verbose_name=_("Texto alternativo"))
    caption = models.CharField(max_length=255, blank=True, verbose_name=_("Pie de foto"))
    credits = models.CharField(max_length=150, blank=True, verbose_name=_("Créditos / Autor"))
    is_cover = models.BooleanField(default=False, db_index=True, verbose_name=_("Portada"))
    order = models.PositiveSmallIntegerField(default=0, verbose_name=_("Orden"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_cover", "order", "id"]
        verbose_name = _("Foto de receta")
        verbose_name_plural = _("Fotos de recetas")

    def save(self, *args, **kwargs):
        if self.image and not getattr(self.image, "_committed", True):
            variants, (w, h) = process_image_variants(self.image, widths=VARIANT_WIDTHS)
            self.width = w
            self.height = h
            self.image.save(variants["large"].name, variants["large"], save=False)
            self.image_medium.save(variants["medium"].name, variants["medium"], save=False)
            self.image_thumb.save(variants["thumb"].name, variants["thumb"], save=False)

        super().save(*args, **kwargs)

        if self.is_cover and self.recipe_id:
            RecipeMedia.objects.filter(recipe_id=self.recipe_id, is_cover=True).exclude(pk=self.pk).update(is_cover=False)

    @property
    def srcset(self) -> str:
        """Atributo HTML srcset con las variantes disponibles (400w, 800w, 1600w)."""
        parts = []
        if self.image_thumb:
            parts.append(f"{self.image_thumb.url} 400w")
        if self.image_medium:
            parts.append(f"{self.image_medium.url} 800w")
        if self.image:
            parts.append(f"{self.image.url} 1600w")
        return ", ".join(parts)

    @property
    def effective_alt(self) -> str:
        return self.alt_text or self.caption or self.recipe.name

    def __str__(self) -> str:
        label = "Portada" if self.is_cover else f"Foto #{self.order}"
        return f"{self.recipe.name} — {label}"
