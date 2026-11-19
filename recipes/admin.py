from django.contrib import admin
from django.utils.html import format_html

from .models import (
    IngredientGroup,
    Recipe,
    RecipeCategory,
    RecipeIngredient,
    RecipeMedia,
    RecipeStep,
    RecipeTag,
    Utensil,
)


class IngredientGroupInline(admin.TabularInline):
    model = IngredientGroup
    extra = 0


class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 1
    autocomplete_fields = ("food",)
    fields = ("group", "order", "food", "household_quantity", "household_measure", "quantity_g", "notes")


class RecipeStepInline(admin.TabularInline):
    model = RecipeStep
    extra = 1
    fields = ("order", "instruction", "tip", "timer_seconds", "image", "image_alt")


class RecipeMediaInline(admin.TabularInline):
    model = RecipeMedia
    extra = 1
    fields = ("preview", "image", "is_cover", "order", "alt_text", "caption", "credits")
    readonly_fields = ("preview",)

    @admin.display(description="Vista previa")
    def preview(self, obj):
        if obj.pk and (obj.image_thumb or obj.image):
            url = obj.image_thumb.url if obj.image_thumb else obj.image.url
            return format_html('<img src="{}" alt="" style="max-height:60px;border-radius:4px;">', url)
        return "—"


@admin.register(RecipeCategory)
class RecipeCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "order", "slug")
    list_filter = ("kind",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(RecipeTag)
class RecipeTagAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "slug")
    list_filter = ("kind",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Utensil)
class UtensilAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "user",
        "status",
        "servings",
        "difficulty",
        "cached_kcal_per_serving",
        "cached_sodium_mg_per_serving",
        "created_at",
    )
    list_filter = ("status", "difficulty", "seasonality", "categories", "tags")
    search_fields = ("name", "description", "slug")
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ("categories", "tags", "utensils")
    readonly_fields = (
        "cached_total_weight_g",
        "cached_kcal_per_serving",
        "cached_proteins_per_serving",
        "cached_carbs_per_serving",
        "cached_lipids_per_serving",
        "cached_fiber_per_serving",
        "cached_sodium_mg_per_serving",
        "cached_potassium_mg_per_serving",
        "cached_glycemic_load_per_serving",
        "created_at",
        "updated_at",
    )
    inlines = [RecipeMediaInline, IngredientGroupInline, RecipeIngredientInline, RecipeStepInline]
    fieldsets = (
        ("Datos básicos", {
            "fields": ("name", "slug", "user", "status", "description", "servings", "video_url")
        }),
        ("Tiempos y clasificación", {
            "fields": (
                ("prep_time_min", "cook_time_min", "rest_time_min"),
                ("difficulty", "cost_level", "seasonality"),
                "cooked_weight_g",
                "categories",
                "tags",
                "utensils",
            )
        }),
        ("Preparación (texto libre heredado)", {
            "classes": ("collapse",),
            "fields": ("instructions",),
        }),
        ("Caché nutricional (por ración)", {
            "fields": (
                ("cached_total_weight_g", "cached_kcal_per_serving"),
                ("cached_proteins_per_serving", "cached_carbs_per_serving", "cached_lipids_per_serving", "cached_fiber_per_serving"),
                ("cached_sodium_mg_per_serving", "cached_potassium_mg_per_serving", "cached_glycemic_load_per_serving"),
            )
        }),
        ("Fechas", {
            "classes": ("collapse",),
            "fields": ("created_at", "updated_at"),
        }),
    )
