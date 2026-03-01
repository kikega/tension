from django import forms
from .models import Food, FoodCategory, Recipe


class FoodForm(forms.ModelForm):
    """Formulario para dar de alta un alimento con su composición nutricional."""

    class Meta:
        model = Food
        fields = [
            "category", "name", "description", "seasonality",
            "edible_portion", "nutritional_rating",
            "energy_kcal", "proteins_g", "lipids_g", "cholesterol_mg",
            "carbohydrates_g", "fiber_g", "water_g",
            "calcium_mg", "iron_mg", "iodine_ug", "magnesium_mg",
            "zinc_mg", "sodium_mg", "potassium_mg", "phosphorus_mg", "selenium_ug",
            "thiamine_mg", "riboflavin_mg", "vitamin_b6_mg", "folate_ug",
            "vitamin_b12_ug", "vitamin_c_mg", "vitamin_a_ug", "vitamin_d_ug", "vitamin_e_mg",
        ]
        widgets = {
            "category": forms.Select(attrs={"class": "form-select"}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "seasonality": forms.Select(attrs={"class": "form-select"}),
            "edible_portion": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "nutritional_rating": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        nutrient_fields = [
            "energy_kcal", "proteins_g", "lipids_g", "cholesterol_mg",
            "carbohydrates_g", "fiber_g", "water_g",
            "calcium_mg", "iron_mg", "iodine_ug", "magnesium_mg",
            "zinc_mg", "sodium_mg", "potassium_mg", "phosphorus_mg", "selenium_ug",
            "thiamine_mg", "riboflavin_mg", "vitamin_b6_mg", "folate_ug",
            "vitamin_b12_ug", "vitamin_c_mg", "vitamin_a_ug", "vitamin_d_ug", "vitamin_e_mg",
        ]
        for field in nutrient_fields:
            self.fields[field].widget = forms.NumberInput(attrs={"class": "form-control", "step": "0.01"})
            self.fields[field].required = False


class RecipeForm(forms.ModelForm):
    """Formulario básico de receta; los ingredientes se gestionan desde el admin."""

    class Meta:
        model = Recipe
        fields = ["name", "description", "instructions", "servings"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "instructions": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
            "servings": forms.NumberInput(attrs={"class": "form-control"}),
        }
