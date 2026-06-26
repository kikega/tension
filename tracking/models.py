from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from decimal import Decimal
from typing import Optional


class PhysicalActivity(models.Model):
    """Catálogo de actividades físicas configurables por el usuario."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_("Usuario"))
    name = models.CharField(max_length=100, verbose_name=_("Nombre"))
    description = models.TextField(blank=True, verbose_name=_("Descripción"))
    met_value = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        default=Decimal("3.0"),
        null=True,
        blank=True,
        verbose_name=_("Valor MET")
    )
    default_not_tracked_by_watch = models.BooleanField(
        default=False,
        verbose_name=_("No registrada por reloj por defecto")
    )

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
    lean_mass_kg = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Masa magra (kg)"),
        validators=[MinValueValidator(Decimal("0.0"))],
    )
    fat_mass_kg = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Masa grasa (kg)"),
        validators=[MinValueValidator(Decimal("0.0"))],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self) -> str:
        return f"{self.date} - {self.weight} kg"

    @property
    def imc(self) -> Optional[float]:
        """Calcula el Índice de Masa Corporal (IMC)."""
        if self.user and self.user.height_cm and self.weight:
            height_m = float(self.user.height_cm) / 100.0
            if height_m > 0:
                return round(float(self.weight) / (height_m * height_m), 2)
        return None

    @property
    def imc_classification(self) -> Optional[str]:
        """Clasifica el IMC para el análisis de obesidad."""
        val = self.imc
        if val is None:
            return None
        if val < 18.5:
            return "Bajo peso"
        elif val < 25.0:
            return "Normal"
        elif val < 30.0:
            return "Sobrepeso"
        else:
            return "Obesidad"


class PhysicalActivityLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_("Usuario"))
    activity = models.ForeignKey(PhysicalActivity, on_delete=models.CASCADE, verbose_name=_("Actividad física"))
    date = models.DateField(default=timezone.now, verbose_name=_("Fecha"))
    duration_minutes = models.PositiveIntegerField(verbose_name=_("Duración (minutos)"))
    notes = models.TextField(blank=True, verbose_name=_("Notas"))
    estimated_calories = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Calorías estimadas (kcal)"))
    not_tracked_by_watch = models.BooleanField(default=False, verbose_name=_("No registrada por reloj"))

    class Meta:
        ordering = ["-date"]
        verbose_name = _("Registro de Ejercicio")
        verbose_name_plural = _("Registros de Ejercicio")

    def __str__(self) -> str:
        return f"{self.date} - {self.activity.name} ({self.duration_minutes} min)"

    def calculate_estimated_calories(self) -> int:
        """Calcula las calorías estimadas de la actividad basadas en el peso del usuario y el MET."""
        if not self.activity or not self.activity.met_value:
            return 0
        
        # Buscar el peso más cercano a la fecha de la actividad
        weight_measurement = WeightMeasurement.objects.filter(
            user=self.user,
            date__lte=self.date
        ).order_by("-date", "-created_at").first()
        
        # Si no hay peso antes de la fecha, buscar el primero disponible
        if not weight_measurement:
            weight_measurement = WeightMeasurement.objects.filter(
                user=self.user
            ).order_by("date", "created_at").first()
            
        weight = float(weight_measurement.weight) if weight_measurement else 70.0  # fallback a 70kg
        
        met = float(self.activity.met_value)
        duration_hours = self.duration_minutes / 60.0
        
        # Fórmula: MET * peso (kg) * duración (horas)
        return int(met * weight * duration_hours)

    def save(self, *args, **kwargs):
        # Si no se ha especificado not_tracked_by_watch al crear, heredar del tipo de actividad
        if self.pk is None and self.activity:
            self.not_tracked_by_watch = self.activity.default_not_tracked_by_watch
            
        # Calcular calorías si no se han establecido
        if self.estimated_calories is None or self.estimated_calories == 0:
            self.estimated_calories = self.calculate_estimated_calories()
            
        super().save(*args, **kwargs)


class FoodLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_("Usuario"))
    date = models.DateField(default=timezone.now, verbose_name=_("Fecha"))
    meal_type = models.CharField(max_length=100, verbose_name=_("Tipo de comida"))
    eaten_out = models.BooleanField(default=False, verbose_name=_("Comida fuera de casa"))
    notes = models.TextField(blank=True, verbose_name=_("Notas"))

    class Meta:
        ordering = ["-date"]
        verbose_name = _("Registro de Alimentación")
        verbose_name_plural = _("Registros de Alimentación")

    def __str__(self) -> str:
        return f"{self.date} - {self.meal_type}"

    def get_nutritional_totals(self) -> dict:
        """Calcula los macros totales (calorías, proteínas, lípidos, carbohidratos) del registro."""
        totals = {
            "calories": 0.0,
            "proteins": 0.0,
            "lipids": 0.0,
            "carbs": 0.0,
        }
        for item in self.items.select_related("food", "recipe").all():
            if item.food and item.quantity_g:
                factor = float(item.quantity_g) / 100.0
                if item.food.energy_kcal is not None:
                    totals["calories"] += float(item.food.energy_kcal) * factor
                if item.food.proteins_g is not None:
                    totals["proteins"] += float(item.food.proteins_g) * factor
                if item.food.lipids_g is not None:
                    totals["lipids"] += float(item.food.lipids_g) * factor
                if item.food.carbohydrates_g is not None:
                    totals["carbs"] += float(item.food.carbohydrates_g) * factor
            elif item.recipe and item.servings:
                recipe_nutrition = item.recipe.calculate_nutrition()
                factor = float(item.servings) / float(item.recipe.servings) if item.recipe.servings else float(item.servings)
                totals["calories"] += float(recipe_nutrition.get('energy_kcal', 0) or 0) * factor
                totals["proteins"] += float(recipe_nutrition.get('proteins_g', 0) or 0) * factor
                totals["lipids"] += float(recipe_nutrition.get('lipids_g', 0) or 0) * factor
                totals["carbs"] += float(recipe_nutrition.get('carbohydrates_g', 0) or 0) * factor
        if self.eaten_out:
            if totals["calories"] > 0:
                totals["calories"] = totals["calories"] * 1.30 + 500.0
            else:
                totals["calories"] = 800.0
        return totals

    def get_total_calories(self) -> float:
        """Calcula las kilocalorías totales sumando los ingredientes del registro."""
        return self.get_nutritional_totals()["calories"]

    def get_glycemic_load(self) -> dict:
        """
        Calcula la carga glucémica (CG) total acumulada de la ingesta de comida.
        Retorna un diccionario con:
          - 'cg': valor total de la carga glucémica de la ingesta (float)
          - 'has_missing_ig': si algún ítem contiene alimentos con carbohidratos que no tienen IG
        """
        total_cg = 0.0
        has_missing_ig = False
        for item in self.items.all():
            item_cg_data = item.get_glycemic_load()
            total_cg += item_cg_data["cg"]
            if item_cg_data["has_missing_ig"]:
                has_missing_ig = True
        return {
            "cg": round(total_cg, 2),
            "has_missing_ig": has_missing_ig
        }


class FoodLogItem(models.Model):
    """Elemento individual ingerido dentro de un registro de alimentación."""

    food_log = models.ForeignKey(FoodLog, related_name="items", on_delete=models.CASCADE)
    food = models.ForeignKey("nutrition.Food", on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Alimento"))
    recipe = models.ForeignKey("nutrition.Recipe", on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Receta"))
    quantity_g = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, verbose_name=_("Cantidad (g)"))
    servings = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name=_("Raciones (Receta)"))

    class Meta:
        verbose_name = _("Ingrediente del Registro")
        verbose_name_plural = _("Ingredientes del Registro")

    def __str__(self) -> str:
        if self.food:
            return f"{self.food.name} - {self.quantity_g}g"
        elif self.recipe:
            return f"Receta: {self.recipe.name} - {self.servings} raciones"
        return "Ítem Desconocido"

    def get_nutritional_totals(self) -> dict:
        """Calcula los macros totales de este ítem (alimento o receta)."""
        totals = {
            "calories": 0.0,
            "proteins": 0.0,
            "lipids": 0.0,
            "carbs": 0.0,
        }
        if self.food and self.quantity_g:
            factor = float(self.quantity_g) / 100.0
            if self.food.energy_kcal is not None:
                totals["calories"] = float(self.food.energy_kcal) * factor
            if self.food.proteins_g is not None:
                totals["proteins"] = float(self.food.proteins_g) * factor
            if self.food.lipids_g is not None:
                totals["lipids"] = float(self.food.lipids_g) * factor
            if self.food.carbohydrates_g is not None:
                totals["carbs"] = float(self.food.carbohydrates_g) * factor
        elif self.recipe and self.servings:
            recipe_nutrition = self.recipe.calculate_nutrition()
            factor = float(self.servings) / float(self.recipe.servings) if self.recipe.servings else float(self.servings)
            totals["calories"] = float(recipe_nutrition.get('energy_kcal', 0) or 0) * factor
            totals["proteins"] = float(recipe_nutrition.get('proteins_g', 0) or 0) * factor
            totals["lipids"] = float(recipe_nutrition.get('lipids_g', 0) or 0) * factor
            totals["carbs"] = float(recipe_nutrition.get('carbohydrates_g', 0) or 0) * factor
        return totals

    def get_glycemic_load(self) -> dict:
        """
        Calcula la carga glucémica (CG) de este ítem (alimento o receta).
        Retorna un diccionario con:
          - 'cg': valor de la CG (float)
          - 'has_missing_ig': si falta algún IG en el alimento o receta
        """
        cg = 0.0
        has_missing_ig = False
        if self.food:
            carbs = float(self.food.carbohydrates_g or 0)
            if carbs > 0:
                if self.food.glycemic_index is not None:
                    portion_carbs = carbs * (float(self.quantity_g or 0) / 100.0)
                    cg = (float(self.food.glycemic_index) * portion_carbs) / 100.0
                else:
                    has_missing_ig = True
        elif self.recipe and self.servings:
            recipe_cg_data = self.recipe.calculate_glycemic_load()
            total_recipe_servings = float(self.recipe.servings or 1)
            factor = float(self.servings) / total_recipe_servings
            cg = recipe_cg_data["total_cg"] * factor
            has_missing_ig = recipe_cg_data["has_missing_ig"]
        return {
            "cg": round(cg, 2),
            "has_missing_ig": has_missing_ig
        }


class DailyActivityLog(models.Model):
    """Registro de actividad diaria (pasos, calorías activas/pasivas del Apple Watch, etc.)."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_("Usuario"))
    date = models.DateField(default=timezone.now, verbose_name=_("Fecha"))
    active_calories = models.PositiveIntegerField(default=0, verbose_name=_("Calorías Activas (kcal)"))
    resting_calories = models.PositiveIntegerField(default=0, verbose_name=_("Calorías en Reposo (kcal)"))
    steps = models.PositiveIntegerField(default=0, verbose_name=_("Pasos"))
    distance_km = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"), verbose_name=_("Distancia (km)"))
    notes = models.TextField(blank=True, verbose_name=_("Notas"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        unique_together = ("user", "date")
        verbose_name = _("Actividad Diaria")
        verbose_name_plural = _("Actividades Diarias")

    def __str__(self) -> str:
        return f"{self.date} — {self.user.email} (Pasos: {self.steps})"

    @property
    def extra_exercise_calories(self) -> int:
        """Calorías de ejercicios no registrados por el reloj (Karate, etc.)."""
        exercises = PhysicalActivityLog.objects.filter(
            user=self.user,
            date=self.date,
            not_tracked_by_watch=True
        )
        return sum(log.estimated_calories or 0 for log in exercises)

    def get_total_calories_burned(self) -> int:
        """Gasto calórico total = calorías activas + calorías pasivas + ejercicios no registrados por el reloj."""
        return self.active_calories + self.resting_calories + self.extra_exercise_calories

    def get_caloric_balance(self) -> float:
        """Balance calórico = Calorías consumidas - Gasto calórico total."""
        # Calorías ingeridas de ese día
        food_logs = FoodLog.objects.filter(user=self.user, date=self.date)
        total_intake = sum(log.get_total_calories() for log in food_logs)
        return float(total_intake) - float(self.get_total_calories_burned())
