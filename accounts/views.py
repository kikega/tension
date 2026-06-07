from django.shortcuts import render
from django.views.generic import UpdateView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from .models import CustomUser
from .forms import UserProfileForm, SignUpForm


class SignUpView(CreateView):
    form_class = SignUpForm
    template_name = "registration/signup.html"
    success_url = reverse_lazy("login")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Tu cuenta ha sido creada con éxito. Ya puedes iniciar sesión.")
        return response

class UserProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = CustomUser
    form_class = UserProfileForm
    template_name = "registration/profile.html"
    success_url = reverse_lazy("dashboard")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Tu perfil ha sido actualizado con éxito.")
        return super().form_valid(form)
