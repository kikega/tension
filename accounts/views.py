from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import UpdateView, CreateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from .models import CustomUser, AccessRequest
from .forms import UserProfileForm, SignUpForm


class SignUpView(CreateView):
    form_class = SignUpForm
    template_name = "registration/signup.html"
    success_url = reverse_lazy("signup_pending")

    def form_valid(self, form):
        # Save user, set active to False
        user = form.save(commit=False)
        user.is_active = False
        user.save()

        # Create access request
        AccessRequest.objects.create(user=user, status='pending')

        # Send email to admin
        admin_emails = [admin[1] for admin in settings.ADMINS]
        if admin_emails:
            subject = f"Nueva solicitud de acceso: {user.email}"
            message = (
                f"Se ha registrado un nuevo usuario en Tension App.\n\n"
                f"Email: {user.email}\n"
                f"Nombre: {user.first_name} {user.last_name}\n"
                f"Fecha de registro: {user.date_joined}\n\n"
                f"Por favor, inicia sesión para revisar y aprobar/rechazar esta solicitud.\n"
            )
            try:
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    admin_emails,
                    fail_silently=True
                )
            except Exception:
                pass

        return redirect("signup_pending")


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


class AccessRequestListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = AccessRequest
    template_name = "accounts/access_requests.html"
    context_object_name = "requests"

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        return AccessRequest.objects.filter(status='pending').select_related('user')


class ApproveAccessRequestView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_staff

    def post(self, request, pk):
        access_request = get_object_or_404(AccessRequest, pk=pk)
        access_request.approve()

        # Send email to user
        subject = "Tu cuenta en Tension App ha sido aprobada"
        message = (
            f"Hola {access_request.user.first_name or 'Usuario'},\n\n"
            f"Tu solicitud de acceso a Tension App ha sido aprobada por el administrador.\n"
            f"Ya puedes iniciar sesión en la plataforma usando tu dirección de correo electrónico.\n\n"
            f"Saludos,\nEl equipo de Tension App"
        )
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [access_request.user.email],
                fail_silently=True
            )
        except Exception:
            pass

        messages.success(request, f"La solicitud de {access_request.user.email} ha sido aprobada.")
        return redirect("access_requests_list")


class RejectAccessRequestView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_staff

    def post(self, request, pk):
        access_request = get_object_or_404(AccessRequest, pk=pk)
        access_request.reject()

        # Send email to user
        subject = "Tu solicitud de acceso a Tension App"
        message = (
            f"Hola {access_request.user.first_name or 'Usuario'},\n\n"
            f"Lamentamos informarte que tu solicitud de acceso a Tension App ha sido rechazada.\n"
            f"Si crees que se trata de un error, por favor contacta con el administrador.\n\n"
            f"Saludos,\nEl equipo de Tension App"
        )
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [access_request.user.email],
                fail_silently=True
            )
        except Exception:
            pass

        messages.warning(request, f"La solicitud de {access_request.user.email} ha sido rechazada.")
        return redirect("access_requests_list")
