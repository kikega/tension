from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from decimal import Decimal


class PhysicalActivity(models.Model):
    """Catálogo de actividades físicas configurables por el usuario."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_("Usuario"))
    name = models.CharField(max_length=100, verbose_name=_("Nombre"))
    description = models.TextField(blank=True, verbose_name=_("Descripción"))

    class Meta:
        ordering = ["name"]
        verbose_name = _("Actividad Física")
        verbose_name_plural = _("Actividades Físicas")

    def __str__(self) -> str:
        return self.name


class Supplement(models.Model):
    """Catálogo de suplementos y complejos vitamínicos del usuario."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_("Usuario"))
    name = models.CharField(max_length=150, verbose_name=_("Nombre"))
    manufacturer = models.CharField(max_length=150, blank=True, verbose_name=_("Fabricante"))
    description = models.TextField(blank=True, verbose_name=_("Descripción"))

    class Meta:
        ordering = ["name"]
        verbose_name = _("Suplemento")
        verbose_name_plural = _("Suplementos")

    def __str__(self) -> str:
        return self.name


class MeasurementSession(models.Model):
    TIME_CHOICES = [
        ("morning", "Mañana"),
        ("night", "Noche"),
    ]
    TYPE_CHOICES = [
        ("intense", "Medición Intensa"),
        ("control", "Medición de Control"),
    ]
    MOOD_CHOICES = [
        ("happy", "Feliz"),
        ("neutral", "Normal"),
        ("stressed", "Estresado"),
        ("sad", "Triste"),
        ("tired", "Cansado"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_("Usuario"))
    date = models.DateField(default=timezone.now, verbose_name=_("Fecha"))
    time_of_day = models.CharField(max_length=10, choices=TIME_CHOICES, verbose_name=_("Momento del día"))
    session_type = models.CharField(max_length=10, choices=TYPE_CHOICES, verbose_name=_("Tipo de medición"))

    # Context Data
    supplements = models.TextField(blank=True, verbose_name=_("Suplementos y Vitaminas"))
    mood = models.CharField(max_length=50, blank=True, choices=MOOD_CHOICES, verbose_name=_("Estado de ánimo"))
    food_type = models.CharField(max_length=100, blank=True, verbose_name=_("Tipo de comida"))
    eaten_out = models.BooleanField(default=False, verbose_name=_("Comida fuera de casa"))
    activity = models.ForeignKey(
        PhysicalActivity,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_("Actividad física"),
    )
    observations = models.TextField(blank=True, verbose_name=_("Observaciones"))

    # Calculated Averages
    avg_systolic = models.FloatField(null=True, blank=True, verbose_name=_("Media Sistólica"))
    avg_diastolic = models.FloatField(null=True, blank=True, verbose_name=_("Media Diastólica"))
    avg_pulse = models.FloatField(null=True, blank=True, verbose_name=_("Media Pulsaciones"))

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self) -> str:
        return f"{self.date} - {self.get_time_of_day_display()} ({self.get_session_type_display()})"

    def calculate_averages(self) -> None:
        """Calcula las medias de sistólica, diastólica y pulsaciones de las lecturas."""
        readings = self.readings.all()
        if readings.exists():
            count = readings.count()
            self.avg_systolic = sum(r.systolic for r in readings) / count
            self.avg_diastolic = sum(r.diastolic for r in readings) / count
            self.avg_pulse = sum(r.pulse for r in readings) / count
            self.save(update_fields=["avg_systolic", "avg_diastolic", "avg_pulse"])


class MeasurementReading(models.Model):
    session = models.ForeignKey(MeasurementSession, related_name="readings", on_delete=models.CASCADE)
    systolic = models.PositiveIntegerField(verbose_name=_("Sistólica"))
    diastolic = models.PositiveIntegerField(verbose_name=_("Diastólica"))
    pulse = models.PositiveIntegerField(verbose_name=_("Pulsaciones"))
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["order"]

    def __str__(self) -> str:
        return f"Lectura {self.order}: {self.systolic}/{self.diastolic} ({self.pulse})"


class SupplementLog(models.Model):
    """Registro de toma de suplementos."""

    TIME_CHOICES = [
        ("morning", "Mañana"),
        ("noon", "Mediodía"),
        ("evening", "Tarde"),
        ("night", "Noche"),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_("Usuario"))
    supplement = models.ForeignKey(Supplement, on_delete=models.CASCADE, verbose_name=_("Suplemento"))
    date = models.DateField(default=timezone.now, verbose_name=_("Fecha"))
    time_of_day = models.CharField(max_length=10, choices=TIME_CHOICES, verbose_name=_("Momento del día"))
    notes = models.TextField(blank=True, verbose_name=_("Notas"))

    class Meta:
        ordering = ["-date"]
        verbose_name = _("Registro de Suplemento")
        verbose_name_plural = _("Registros de Suplementos")

    def __str__(self) -> str:
        return f"{self.date} - {self.supplement.name} ({self.get_time_of_day_display()})"


class WeightMeasurement(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_("Usuario"))
    date = models.DateField(default=timezone.now, verbose_name=_("Fecha"))
    weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name=_("Peso (kg)"),
        validators=[MinValueValidator(Decimal("0.0"))],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self) -> str:
        return f"{self.date} - {self.weight} kg"
