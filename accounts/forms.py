from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import CustomUser

class CustomUserCreationForm(UserCreationForm):

    class Meta:
        model = CustomUser
        fields = ('email',)

class CustomUserChangeForm(UserChangeForm):

    class Meta:
        model = CustomUser
        fields = ('email',)


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ["first_name", "last_name", "gender", "birth_date", "height_cm", "target_weekly_loss_kg"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "gender": forms.Select(attrs={"class": "form-control form-select"}),
            "birth_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "height_cm": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Ej. 175"}),
            "target_weekly_loss_kg": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "placeholder": "Ej. 0.5"}),
        }


class SignUpForm(UserCreationForm):
    gender = forms.ChoiceField(
        choices=CustomUser.GENDER_CHOICES,
        label="Género",
        required=False,
        widget=forms.Select(attrs={"class": "form-control form-select"})
    )
    birth_date = forms.DateField(
        label="Fecha de nacimiento",
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )
    height_cm = forms.IntegerField(
        label="Altura (cm)",
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "Ej. 175"})
    )
    target_weekly_loss_kg = forms.DecimalField(
        label="Objetivo de pérdida semanal (kg)",
        required=False,
        initial=0.50,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "placeholder": "Ej. 0.5"})
    )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ("email", "first_name", "last_name", "gender", "birth_date", "height_cm", "target_weekly_loss_kg")
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre"}),
            "last_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Apellidos"}),
        }
