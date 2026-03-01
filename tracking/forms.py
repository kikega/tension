from django import forms
from django.forms import inlineformset_factory
from .models import (
    MeasurementSession,
    MeasurementReading,
    WeightMeasurement,
    Supplement,
    SupplementLog,
    PhysicalActivity,
)


class MeasurementSessionForm(forms.ModelForm):
    """Formulario para registrar una sesión de medición de tensión arterial."""

    class Meta:
        model = MeasurementSession
        exclude = ("user", "created_at", "avg_systolic", "avg_diastolic", "avg_pulse")
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "time_of_day": forms.Select(attrs={"class": "form-select"}),
            "session_type": forms.Select(attrs={"class": "form-select"}),
            "supplements": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "mood": forms.Select(attrs={"class": "form-select"}),
            "food_type": forms.TextInput(attrs={"class": "form-control"}),
            "eaten_out": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "activity": forms.Select(attrs={"class": "form-select"}),
            "observations": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["activity"].queryset = PhysicalActivity.objects.filter(user=user)
        self.fields["activity"].empty_label = "— Sin actividad —"


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
        fields = ["date", "weight"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "weight": forms.NumberInput(attrs={"class": "form-control", "step": "0.1", "placeholder": "Ej. 80.5"}),
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
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }
