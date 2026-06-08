from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .forms import CustomUserCreationForm, CustomUserChangeForm
from .models import CustomUser, AccessRequest


@admin.action(description="Aprobar usuarios seleccionados (Activar)")
def approve_users(modeladmin, request, queryset):
    updated = queryset.update(is_active=True)
    for user in queryset:
        if hasattr(user, 'access_request'):
            req = user.access_request
            req.status = 'approved'
            req.save()
    modeladmin.message_user(request, f"Se han aprobado y activado {updated} usuarios.")


@admin.action(description="Rechazar usuarios seleccionados (Desactivar)")
def reject_users(modeladmin, request, queryset):
    updated = queryset.update(is_active=False)
    for user in queryset:
        if hasattr(user, 'access_request'):
            req = user.access_request
            req.status = 'rejected'
            req.save()
    modeladmin.message_user(request, f"Se han rechazado y desactivado {updated} usuarios.")


class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser
    list_display = ['email', 'is_staff', 'is_active', 'date_joined']
    list_filter = ['is_staff', 'is_active', 'date_joined']
    actions = [approve_users, reject_users]
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'gender', 'birth_date', 'height_cm', 'target_weekly_loss_kg')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password', 'is_staff', 'is_active')}
        ),
    )
    search_fields = ['email']
    ordering = ['email']


@admin.action(description="Aprobar solicitudes seleccionadas")
def approve_requests(modeladmin, request, queryset):
    count = 0
    for req in queryset:
        if req.status == 'pending':
            req.approve()
            count += 1
    modeladmin.message_user(request, f"Se han aprobado {count} solicitudes de acceso.")


@admin.action(description="Rechazar solicitudes seleccionadas")
def reject_requests(modeladmin, request, queryset):
    count = 0
    for req in queryset:
        if req.status == 'pending':
            req.reject()
            count += 1
    modeladmin.message_user(request, f"Se han rechazado {count} solicitudes de acceso.")


class AccessRequestAdmin(admin.ModelAdmin):
    list_display = ['get_user_email', 'status', 'created_at', 'updated_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user__email']
    actions = [approve_requests, reject_requests]

    def get_user_email(self, obj):
        return obj.user.email
    get_user_email.short_description = 'Usuario'


admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(AccessRequest, AccessRequestAdmin)
