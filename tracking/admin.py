from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import (
    FoodLog,
    FoodLogItem,
    MeasurementReading,
    MeasurementSession,
    PhysicalActivity,
    PhysicalActivityLog,
    Supplement,
    SupplementLog,
    WeightMeasurement,
)


# ---------------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------------

class MeasurementReadingInline(admin.TabularInline):
    """Lecturas de tensión/pulso dentro de una sesión de medición."""

    model = MeasurementReading
    extra = 3
    min_num = 1
    max_num = 10
    fields = ("order", "systolic", "diastolic", "pulse")


class FoodLogItemInline(admin.TabularInline):
    """Alimentos / Recetas ingeridos dentro de un registro de alimentación."""

    model = FoodLogItem
    extra = 1
    min_num = 0
    autocomplete_fields = []          # habilitar si Food/Recipe usan search_fields
    fields = ("food", "quantity_g", "recipe", "servings")
    verbose_name = _("Ítem ingerido")
    verbose_name_plural = _("Ítems ingeridos")


# ---------------------------------------------------------------------------
# MeasurementSession
# ---------------------------------------------------------------------------

@admin.register(MeasurementSession)
class MeasurementSessionAdmin(admin.ModelAdmin):
    """Gestión de sesiones de medición de tensión."""

    list_display = (
        "date",
        "user",
        "time_of_day",
        "session_type",
        "avg_systolic",
        "avg_diastolic",
        "avg_pulse",
        "mood",
    )
    list_filter = ("session_type", "time_of_day", "mood", "user")
    search_fields = ("user__username", "observations")
    date_hierarchy = "date"
    readonly_fields = ("avg_systolic", "avg_diastolic", "avg_pulse", "created_at")
    inlines = [MeasurementReadingInline]

    def save_related(self, request, form, formsets, change):
        """Recalcula las medias tras guardar las lecturas inline."""
        super().save_related(request, form, formsets, change)
        form.instance.calculate_averages()


# ---------------------------------------------------------------------------
# MeasurementReading
# ---------------------------------------------------------------------------

@admin.register(MeasurementReading)
class MeasurementReadingAdmin(admin.ModelAdmin):
    """Vista directa de lecturas individuales de tensión."""

    list_display = ("session", "order", "systolic", "diastolic", "pulse")
    list_filter = ("session__user",)
    search_fields = ("session__user__username",)
    ordering = ("session", "order")


# ---------------------------------------------------------------------------
# PhysicalActivity  (catálogo)
# ---------------------------------------------------------------------------

@admin.register(PhysicalActivity)
class PhysicalActivityAdmin(admin.ModelAdmin):
    """Catálogo de actividades físicas."""

    list_display = ("name", "user", "description")
    list_filter = ("user",)
    search_fields = ("name", "description")
    ordering = ("name",)


# ---------------------------------------------------------------------------
# PhysicalActivityLog
# ---------------------------------------------------------------------------

@admin.register(PhysicalActivityLog)
class PhysicalActivityLogAdmin(admin.ModelAdmin):
    """Histórico de ejercicio físico registrado."""

    list_display = ("date", "user", "activity", "duration_minutes")
    list_filter = ("user", "activity")
    search_fields = ("user__username", "activity__name", "notes")
    date_hierarchy = "date"
    ordering = ("-date",)


# ---------------------------------------------------------------------------
# Supplement  (catálogo)
# ---------------------------------------------------------------------------

@admin.register(Supplement)
class SupplementAdmin(admin.ModelAdmin):
    """Catálogo de suplementos y vitamínicos."""

    list_display = ("name", "user", "manufacturer")
    list_filter = ("user",)
    search_fields = ("name", "manufacturer", "description")
    ordering = ("name",)


# ---------------------------------------------------------------------------
# SupplementLog
# ---------------------------------------------------------------------------

@admin.register(SupplementLog)
class SupplementLogAdmin(admin.ModelAdmin):
    """Histórico de tomas de suplementos."""

    list_display = ("date", "user", "supplement", "time_of_day")
    list_filter = ("user", "supplement", "time_of_day")
    search_fields = ("user__username", "supplement__name", "notes")
    date_hierarchy = "date"
    ordering = ("-date",)


# ---------------------------------------------------------------------------
# WeightMeasurement
# ---------------------------------------------------------------------------

@admin.register(WeightMeasurement)
class WeightMeasurementAdmin(admin.ModelAdmin):
    """Histórico de pesajes del usuario."""

    list_display = ("date", "user", "weight", "created_at")
    list_filter = ("user",)
    search_fields = ("user__username",)
    date_hierarchy = "date"
    readonly_fields = ("created_at",)
    ordering = ("-date",)


# ---------------------------------------------------------------------------
# FoodLog  ← PRINCIPAL: gestión del histórico de ingestas
# ---------------------------------------------------------------------------

@admin.register(FoodLog)
class FoodLogAdmin(admin.ModelAdmin):
    """
    Histórico de ingestas de alimentos.

    Permite crear, editar y eliminar registros diarios de alimentación
    junto con sus ítems (alimentos / recetas ingeridos) directamente
    desde el inline ``FoodLogItemInline``.
    """

    list_display = ("date", "user", "meal_type", "eaten_out", "total_calories_display")
    list_filter = ("user", "meal_type", "eaten_out")
    search_fields = ("user__username", "meal_type", "notes")
    date_hierarchy = "date"
    ordering = ("-date",)
    inlines = [FoodLogItemInline]

    # Organización del formulario de detalle
    fieldsets = (
        (None, {
            "fields": ("user", "date", "meal_type", "eaten_out"),
        }),
        (_("Notas"), {
            "fields": ("notes",),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description=_("Calorías totales (kcal)"))
    def total_calories_display(self, obj: FoodLog) -> str:
        """Muestra las kcal totales calculadas para la lista."""
        kcal = obj.get_total_calories()
        return f"{kcal:.1f} kcal" if kcal else "—"


# ---------------------------------------------------------------------------
# FoodLogItem  (acceso directo para edición/eliminación individual)
# ---------------------------------------------------------------------------

@admin.register(FoodLogItem)
class FoodLogItemAdmin(admin.ModelAdmin):
    """
    Vista directa de ítems individuales de ingesta.

    Permite editar o eliminar un alimento / receta de un registro
    sin necesidad de abrir el ``FoodLog`` padre.
    """

    list_display = ("food_log", "food", "quantity_g", "recipe", "servings")
    list_filter = ("food_log__user", "food_log__meal_type")
    search_fields = (
        "food_log__user__username",
        "food__name",
        "recipe__name",
    )
    ordering = ("-food_log__date",)
    raw_id_fields = ("food_log", "food", "recipe")
