from django.contrib import admin

from .models import Allergen, Food, FoodCategory, HouseholdMeasure, NutritionalReference


class HouseholdMeasureInline(admin.TabularInline):
    model = HouseholdMeasure
    extra = 1


@admin.register(Allergen)
class AllergenAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "icon")
    search_fields = ("name", "code")
    prepopulated_fields = {"code": ("name",)}


@admin.register(FoodCategory)
class FoodCategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Food)
class FoodAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "seasonality", "data_source", "glycemic_index", "energy_kcal", "proteins_g", "carbohydrates_g", "lipids_g")
    list_filter = ("category", "seasonality", "data_source", "allergens")
    search_fields = ("name", "external_id")
    filter_horizontal = ("allergens",)
    inlines = [HouseholdMeasureInline]
    fieldsets = (
        ("Datos Generales", {
            "fields": ("category", "name", "description", "seasonality", "edible_portion", "nutritional_rating", "allergens", "data_source", "external_id")
        }),
        ("Macronutrientes", {
            "fields": ("energy_kcal", "proteins_g", "lipids_g", "cholesterol_mg", "carbohydrates_g", "glycemic_index", "fiber_g", "water_g")
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
