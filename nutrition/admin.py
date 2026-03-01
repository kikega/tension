from django.contrib import admin
from .models import FoodCategory, Food, NutritionalReference, Recipe, RecipeIngredient


class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 1


@admin.register(FoodCategory)
class FoodCategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Food)
class FoodAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "seasonality", "energy_kcal", "proteins_g", "carbohydrates_g", "lipids_g")
    list_filter = ("category", "seasonality")
    search_fields = ("name",)
    fieldsets = (
        ("Datos Generales", {
            "fields": ("category", "name", "description", "seasonality", "edible_portion", "nutritional_rating")
        }),
        ("Macronutrientes", {
            "fields": ("energy_kcal", "proteins_g", "lipids_g", "cholesterol_mg", "carbohydrates_g", "fiber_g", "water_g")
        }),
        ("Minerales", {
            "fields": ("calcium_mg", "iron_mg", "iodine_ug", "magnesium_mg", "zinc_mg", "sodium_mg", "potassium_mg", "phosphorus_mg", "selenium_ug")
        }),
        ("Vitaminas", {
            "fields": ("thiamine_mg", "riboflavin_mg", "vitamin_b6_mg", "folate_ug", "vitamin_b12_ug", "vitamin_c_mg", "vitamin_a_ug", "vitamin_d_ug", "vitamin_e_mg")
        }),
    )


@admin.register(NutritionalReference)
class NutritionalReferenceAdmin(admin.ModelAdmin):
    list_display = ("gender", "energy_kcal", "proteins_g", "carbohydrates_g")


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ("name", "servings", "created_at")
    search_fields = ("name",)
    inlines = [RecipeIngredientInline]
