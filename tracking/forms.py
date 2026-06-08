from django import forms
from django.forms import inlineformset_factory
from .models import (
    MeasurementSession,
    MeasurementReading,
    WeightMeasurement,
    Supplement,
    SupplementLog,
    PhysicalActivity,
    PhysicalActivityLog,
    FoodLog,
    FoodLogItem,
)


class MeasurementSessionForm(forms.ModelForm):
    """Formulario para registrar una sesión de medición de tensión arterial."""

    class Meta:
        model = MeasurementSession
        exclude = ("user", "created_at", "avg_systolic", "avg_diastolic", "avg_pulse")
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "time_of_day": forms.Select(attrs={"class": "form-control form-select"}),
            "session_type": forms.Select(attrs={"class": "form-control form-select"}),
            "supplements": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "mood": forms.Select(attrs={"class": "form-control form-select"}),
            "observations": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)


ReadingFormSet = inlineformset_factory(
    MeasurementSession,
    MeasurementReading,
    fields=("systolic", "diastolic", "pulse"),
    extra=3,
    min_num=3,
    max_num=3,
    validate_min=True,
    can_delete=False,
    widgets={
        "systolic": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Sys"}),
        "diastolic": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Dia"}),
        "pulse": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Pulso"}),
    },
)


class WeightMeasurementForm(forms.ModelForm):
    """Formulario para registrar una medición de peso."""

    class Meta:
        model = WeightMeasurement
        fields = ["date", "weight", "lean_mass_kg", "fat_mass_kg"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "weight": forms.NumberInput(attrs={"class": "form-control", "step": "0.1", "placeholder": "Ej. 80.5"}),
            "lean_mass_kg": forms.NumberInput(attrs={"class": "form-control", "step": "0.1", "placeholder": "Ej. 62.0 (Opcional)"}),
            "fat_mass_kg": forms.NumberInput(attrs={"class": "form-control", "step": "0.1", "placeholder": "Ej. 18.5 (Opcional)"}),
        }


class SupplementForm(forms.ModelForm):
    """Formulario para crear un suplemento en el catálogo del usuario."""

    class Meta:
        model = Supplement
        fields = ["name", "manufacturer", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "manufacturer": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class SupplementLogForm(forms.ModelForm):
    """Formulario para registrar la toma de un suplemento."""

    class Meta:
        model = SupplementLog
        fields = ["supplement", "date", "time_of_day", "notes"]
        widgets = {
            "supplement": forms.Select(attrs={"class": "form-select"}),
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "time_of_day": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["supplement"].queryset = Supplement.objects.filter(user=user)


class PhysicalActivityForm(forms.ModelForm):
    """Formulario para crear/editar una actividad física en el catálogo del usuario."""

    class Meta:
        model = PhysicalActivity
        fields = ["name", "description", "met_value", "default_not_tracked_by_watch"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "met_value": forms.NumberInput(attrs={"class": "form-control", "step": "0.1", "placeholder": "Ej. 8.0"}),
            "default_not_tracked_by_watch": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class PhysicalActivityLogForm(forms.ModelForm):
    """Formulario para registrar el inicio de una actividad física."""

    class Meta:
        model = PhysicalActivityLog
        fields = ["activity", "date", "duration_minutes", "not_tracked_by_watch", "notes"]
        widgets = {
            "activity": forms.Select(attrs={"class": "form-control form-select"}),
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "duration_minutes": forms.NumberInput(attrs={"class": "form-control"}),
            "not_tracked_by_watch": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["activity"].queryset = PhysicalActivity.objects.filter(user=user)


from .models import DailyActivityLog

class DailyActivityLogForm(forms.ModelForm):
    """Formulario para registrar la actividad diaria del Apple Watch."""

    class Meta:
        model = DailyActivityLog
        fields = ["date", "active_calories", "resting_calories", "steps", "distance_km", "notes"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "active_calories": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Ej. 400"}),
            "resting_calories": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Ej. 1800"}),
            "steps": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Ej. 10000"}),
            "distance_km": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "placeholder": "Ej. 6.5"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        kwargs.pop("user", None)
        super().__init__(*args, **kwargs)


class FoodLogForm(forms.ModelForm):
    """Formulario para registrar una comida."""

    class Meta:
        model = FoodLog
        fields = ["date", "meal_type", "eaten_out", "notes"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "meal_type": forms.TextInput(attrs={"class": "form-control"}),
            "eaten_out": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

class FoodLogItemForm(forms.ModelForm):
    class Meta:
        model = FoodLogItem
        fields = ("food", "recipe", "quantity_g", "servings")
        widgets = {
            "food": forms.Select(attrs={"class": "form-control form-select"}),
            "recipe": forms.Select(attrs={"class": "form-control form-select"}),
            "quantity_g": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Gramos"}),
            "servings": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Raciones"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        from nutrition.models import Recipe
        from django.db.models import Q
        if user:
            self.fields["recipe"].queryset = Recipe.objects.filter(Q(user__isnull=True) | Q(user=user))
        else:
            self.fields["recipe"].queryset = Recipe.objects.filter(user__isnull=True)

FoodLogItemFormSet = inlineformset_factory(
    FoodLog,
    FoodLogItem,
    form=FoodLogItemForm,
    extra=1,
    can_delete=True,
)
