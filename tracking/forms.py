from django import forms
from django.forms import inlineformset_factory
from .models import MeasurementSession, MeasurementReading, WeightMeasurement

class MeasurementSessionForm(forms.ModelForm):
    class Meta:
        model = MeasurementSession
        exclude = ('user', 'created_at', 'avg_systolic', 'avg_diastolic', 'avg_pulse')
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'time_of_day': forms.Select(attrs={'class': 'form-select'}),
            'session_type': forms.Select(attrs={'class': 'form-select'}),
            'supplements': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'mood': forms.Select(attrs={'class': 'form-select'}),
            'food_type': forms.TextInput(attrs={'class': 'form-control'}),
            'activity_type': forms.TextInput(attrs={'class': 'form-control'}),
            'observations': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

ReadingFormSet = inlineformset_factory(
    MeasurementSession,
    MeasurementReading,
    fields=('systolic', 'diastolic', 'pulse'),
    extra=3,
    min_num=3,
    max_num=3,
    validate_min=True,
    can_delete=False,
    widgets={
        'systolic': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Sys'}),
        'diastolic': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Dia'}),
        'pulse': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Pulse'}),
    }
)

class WeightMeasurementForm(forms.ModelForm):
    class Meta:
        model = WeightMeasurement
        fields = ['date', 'weight']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'placeholder': 'Ej. 80.5'}),
        }
