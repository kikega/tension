from django import forms
from django.forms import inlineformset_factory

from nutrition.models import Food

from .models import Recipe, RecipeIngredient, RecipeMedia


class RecipeIngredientForm(forms.ModelForm):
    class Meta:
        model = RecipeIngredient
        fields = ("food", "quantity_g")
        widgets = {
            "food": forms.Select(attrs={"class": "form-control form-select"}),
            "quantity_g": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Cantidad (g)"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        from django.db.models import Q
        if user:
            self.fields["food"].queryset = Food.objects.filter(
                Q(user__isnull=True) | Q(user=user)
            ).order_by("name")
        else:
            self.fields["food"].queryset = Food.objects.order_by("name")


RecipeIngredientFormSet = inlineformset_factory(
    Recipe,
    RecipeIngredient,
    form=RecipeIngredientForm,
    extra=1,
    can_delete=True,
)


class RecipeMediaForm(forms.ModelForm):
    class Meta:
        model = RecipeMedia
        fields = ("image", "is_cover", "alt_text", "caption", "credits", "order")
        widgets = {
            "image": forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/jpeg,image/png,image/webp"}),
            "is_cover": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "alt_text": forms.TextInput(attrs={"class": "form-control", "placeholder": "Descripción de la foto (accesibilidad)"}),
            "caption": forms.TextInput(attrs={"class": "form-control", "placeholder": "Pie de foto opcional"}),
            "credits": forms.TextInput(attrs={"class": "form-control", "placeholder": "Autor / créditos"}),
            "order": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
        }


RecipeMediaFormSet = inlineformset_factory(
    Recipe,
    RecipeMedia,
    form=RecipeMediaForm,
    extra=1,
    can_delete=True,
)


class RecipeForm(forms.ModelForm):
    class Meta:
        model = Recipe
        fields = ["name", "description", "instructions", "servings", "video_url"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "instructions": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
            "servings": forms.NumberInput(attrs={"class": "form-control"}),
            "video_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://www.youtube.com/watch?v=..."}),
        }
