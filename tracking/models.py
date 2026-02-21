from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from decimal import Decimal

class MeasurementSession(models.Model):
    TIME_CHOICES = [
        ('morning', 'Mañana'),
        ('night', 'Noche'),
    ]
    TYPE_CHOICES = [
        ('intense', 'Medición Intensa'),
        ('control', 'Medición de Control'),
    ]
    MOOD_CHOICES = [ # Example choices, can be expanded or made free text
        ('happy', 'Feliz'),
        ('neutral', 'Normal'),
        ('stressed', 'Estresado'),
        ('sad', 'Triste'),
        ('tired', 'Cansado'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now, verbose_name=_("Fecha"))
    time_of_day = models.CharField(max_length=10, choices=TIME_CHOICES, verbose_name=_("Momento del día"))
    session_type = models.CharField(max_length=10, choices=TYPE_CHOICES, verbose_name=_("Tipo de medición"))
    
    # Context Data
    supplements = models.TextField(blank=True, verbose_name=_("Suplementos y Vitaminas"))
    mood = models.CharField(max_length=50, blank=True, choices=MOOD_CHOICES, verbose_name=_("Estado de ánimo")) # Made choices for consistency
    food_type = models.CharField(max_length=100, blank=True, verbose_name=_("Tipo de comida"))
    activity_type = models.CharField(max_length=100, blank=True, verbose_name=_("Actividad física"))
    observations = models.TextField(blank=True, verbose_name=_("Observaciones"))
    
    # Calculated Averages
    avg_systolic = models.FloatField(null=True, blank=True, verbose_name=_("Media Sistólica"))
    avg_diastolic = models.FloatField(null=True, blank=True, verbose_name=_("Media Diastólica"))
    avg_pulse = models.FloatField(null=True, blank=True, verbose_name=_("Media Pulsaciones"))

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.date} - {self.get_time_of_day_display()} ({self.get_session_type_display()})"

    def calculate_averages(self):
        readings = self.readings.all()
        if readings.exists():
            count = readings.count()
            self.avg_systolic = sum(r.systolic for r in readings) / count
            self.avg_diastolic = sum(r.diastolic for r in readings) / count
            self.avg_pulse = sum(r.pulse for r in readings) / count
            self.save(update_fields=['avg_systolic', 'avg_diastolic', 'avg_pulse'])

class MeasurementReading(models.Model):
    session = models.ForeignKey(MeasurementSession, related_name='readings', on_delete=models.CASCADE)
    systolic = models.PositiveIntegerField(verbose_name=_("Sistólica"))
    diastolic = models.PositiveIntegerField(verbose_name=_("Diastólica"))
    pulse = models.PositiveIntegerField(verbose_name=_("Pulsaciones"))
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Lectura {self.order}: {self.systolic}/{self.diastolic} ({self.pulse})"

class WeightMeasurement(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now, verbose_name=_("Fecha"))
    weight = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        verbose_name=_("Peso (kg)"),
        validators=[MinValueValidator(Decimal('0.0'))]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.date} - {self.weight} kg"
