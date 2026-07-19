from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, CreateView, ListView, UpdateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.db import transaction
from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse
from django.utils import timezone
from datetime import timedelta
import json
import csv

from .models import (
    MeasurementSession,
    WeightMeasurement,
    Supplement,
    SupplementLog,
    PhysicalActivity,
    PhysicalActivityLog,
    FoodLog,
    DailyActivityLog,
)
from nutrition.models import NutritionalReference
from .forms import (
    MeasurementSessionForm,
    ReadingFormSet,
    WeightMeasurementForm,
    SupplementForm,
    SupplementLogForm,
    PhysicalActivityForm,
    PhysicalActivityLogForm,
    FoodLogForm,
    DailyActivityLogForm,
)
from .services.helpers import get_bmr_for_user


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "tracking/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # --- Blood Pressure & Pulse Data ---
        sessions = MeasurementSession.objects.filter(user=self.request.user).order_by("-date", "-created_at")
        context["recent_sessions"] = sessions[:10]

        last_30_sessions = sessions[:30]
        chart_sessions = list(reversed(last_30_sessions))
        dates = [s.date.strftime("%d/%m") for s in chart_sessions]
        bp_data = [[s.avg_diastolic, s.avg_systolic] for s in chart_sessions]
        pulse_data = [s.avg_pulse for s in chart_sessions]

        context["chart_labels"] = json.dumps(dates)
        context["bp_data"] = json.dumps(bp_data)
        context["pulse_data"] = json.dumps(pulse_data)

        # --- Weight Data ---
        weights = WeightMeasurement.objects.filter(user=self.request.user).order_by("-date", "-created_at")
        last_10_weights = list(reversed(weights[:10]))
        weight_dates = [w.date.strftime("%d/%m") for w in last_10_weights]
        weight_values = [float(w.weight) for w in last_10_weights]

        context["weight_labels"] = json.dumps(weight_dates)
        context["weight_data"] = json.dumps(weight_values)

        last_activity = PhysicalActivityLog.objects.filter(user=self.request.user).order_by("-date", "-id").first()
        context["last_session"] = sessions.first()
        context["last_weight"] = weights.first()
        context["last_activity"] = last_activity

        # --- Today's Caloric Balance & Activity (Apple Watch + Karate) ---
        today = timezone.now().date()
        daily_log = DailyActivityLog.objects.filter(user=self.request.user, date=today).first()
        
        # Último peso para calcular el BMR si falta
        last_w = weights.first()
        weight_val = float(last_w.weight) if last_w else 70.0
        
        # Calcular BMR/TMB
        bmr = self.request.user.calculate_bmr(weight_val)
        
        # Ejercicios extras de hoy (Karate, etc. no monitorizados por el reloj)
        exercises_today = PhysicalActivityLog.objects.filter(
            user=self.request.user,
            date=today,
            not_tracked_by_watch=True
        )
        extra_cal = sum(log.estimated_calories or 0 for log in exercises_today)
        
        if not daily_log:
            total_burned_today = bmr + extra_cal
            active_cal = 0
            steps_today = 0
            dist_today = 0.0
        else:
            total_burned_today = daily_log.get_total_calories_burned()
            active_cal = daily_log.active_calories
            bmr = daily_log.resting_calories
            steps_today = daily_log.steps
            dist_today = float(daily_log.distance_km)

        # Si hoy no hay datos de actividad, mostrar el último día con datos reales
        if steps_today == 0 and dist_today == 0.0:
            last_log = DailyActivityLog.objects.filter(
                user=self.request.user
            ).exclude(steps=0, distance_km=0.0).order_by("-date").first()
            if last_log:
                steps_today = last_log.steps
                dist_today = float(last_log.distance_km)
                active_cal = last_log.active_calories

        # Ingesta de hoy
        food_logs_today = FoodLog.objects.filter(user=self.request.user, date=today)
        total_intake_today = sum(log.get_total_calories() for log in food_logs_today)
        
        context["today_intake"] = total_intake_today
        context["today_burned"] = total_burned_today
        context["today_balance"] = total_intake_today - total_burned_today
        context["today_steps"] = steps_today
        context["today_distance"] = dist_today
        context["today_active_calories"] = active_cal
        context["today_resting_calories"] = bmr
        context["today_extra_calories"] = extra_cal
        context["has_daily_log_today"] = (daily_log is not None)

        # --- Food Data (Last 10 Days) ---
        food_qs = FoodLog.objects.filter(user=self.request.user).prefetch_related(
            "items__food", "items__recipe"
        )
        food_dates = food_qs.values_list("date", flat=True).distinct().order_by("-date")[:10]
        recent_food_days = []
        if food_dates:
            food_by_date = {}
            for log in food_qs.filter(date__in=list(food_dates)):
                food_by_date.setdefault(log.date, []).append(log)
            for d in food_dates:
                d_foods = food_by_date.get(d, [])
                totals = {"calories": 0.0, "proteins": 0.0, "lipids": 0.0, "carbs": 0.0}
                for log in d_foods:
                    macros = log.get_nutritional_totals()
                    for k in totals:
                        totals[k] += macros[k]
                recent_food_days.append({"date": d, "totals": totals})
        context["recent_food_days"] = recent_food_days

        return context


class AddMeasurementView(LoginRequiredMixin, CreateView):
    model = MeasurementSession
    form_class = MeasurementSessionForm
    template_name = "tracking/add_measurement.html"
    success_url = reverse_lazy("dashboard")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["readings"] = ReadingFormSet(self.request.POST)
        else:
            context["readings"] = ReadingFormSet()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        readings = context["readings"]
        with transaction.atomic():
            form.instance.user = self.request.user
            self.object = form.save()
            if readings.is_valid():
                readings.instance = self.object
                readings.save()
                for i, reading in enumerate(self.object.readings.all(), start=1):
                    reading.order = i
                    reading.save(update_fields=["order"])
            else:
                return self.form_invalid(form)
        return super().form_valid(form)


class MeasurementSessionUpdateView(LoginRequiredMixin, UpdateView):
    model = MeasurementSession
    form_class = MeasurementSessionForm
    template_name = "tracking/edit_measurement.html"
    success_url = reverse_lazy("history")

    def get_queryset(self):
        return MeasurementSession.objects.filter(user=self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["readings"] = ReadingFormSet(self.request.POST, instance=self.object)
        else:
            context["readings"] = ReadingFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        readings = context["readings"]
        with transaction.atomic():
            form.instance.user = self.request.user
            self.object = form.save()
            if readings.is_valid():
                readings.save()
                for i, reading in enumerate(self.object.readings.all(), start=1):
                    reading.order = i
                    reading.save(update_fields=["order"])
            else:
                return self.form_invalid(form)
        return super().form_valid(form)


class HistoryListView(LoginRequiredMixin, ListView):
    model = MeasurementSession
    template_name = "tracking/history.html"
    context_object_name = "sessions"
    paginate_by = 20

    def get_queryset(self):
        qs = MeasurementSession.objects.filter(user=self.request.user).prefetch_related("readings")
        session_type = self.request.GET.get("type")
        if session_type:
            qs = qs.filter(session_type=session_type)
        return qs.order_by("-date", "-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Añadir errores estadísticos a cada lectura de cada sesión
        # Añadir errores estadísticos a cada lectura y calcular medias por sesión
        for session in context["sessions"]:
            if session.avg_systolic and session.avg_diastolic and session.avg_pulse:
                total_err_abs_sys = total_err_abs_dia = total_err_abs_pul = 0
                total_err_rel_sys = total_err_rel_dia = total_err_rel_pul = 0
                readings_count = 0
                
                for reading in session.readings.all():
                    readings_count += 1
                    # Error absoluto: |valor - media|
                    reading.err_abs_sys = abs(reading.systolic - session.avg_systolic)
                    reading.err_abs_dia = abs(reading.diastolic - session.avg_diastolic)
                    reading.err_abs_pul = abs(reading.pulse - session.avg_pulse)
                    # Error relativo: (|valor - media| / media) * 100
                    reading.err_rel_sys = (reading.err_abs_sys / session.avg_systolic * 100) if session.avg_systolic else 0
                    reading.err_rel_dia = (reading.err_abs_dia / session.avg_diastolic * 100) if session.avg_diastolic else 0
                    reading.err_rel_pul = (reading.err_abs_pul / session.avg_pulse * 100) if session.avg_pulse else 0
                    
                    # Acumular para medias de sesión
                    total_err_abs_sys += reading.err_abs_sys
                    total_err_abs_dia += reading.err_abs_dia
                    total_err_abs_pul += reading.err_abs_pul
                    
                    total_err_rel_sys += reading.err_rel_sys
                    total_err_rel_dia += reading.err_rel_dia
                    total_err_rel_pul += reading.err_rel_pul

                if readings_count > 0:
                    session.avg_err_abs_sys = total_err_abs_sys / readings_count
                    session.avg_err_abs_dia = total_err_abs_dia / readings_count
                    session.avg_err_abs_pul = total_err_abs_pul / readings_count
                    
                    session.avg_err_rel_sys = total_err_rel_sys / readings_count
                    session.avg_err_rel_dia = total_err_rel_dia / readings_count
                    session.avg_err_rel_pul = total_err_rel_pul / readings_count
                    
        return context


class MeasurementHistoryPrintView(HistoryListView):
    """Vista para exportar el historial completo a un formato imprimible."""
    template_name = "tracking/history_print.html"
    paginate_by = None


class WeightMeasurementCreateView(LoginRequiredMixin, CreateView):
    model = WeightMeasurement
    form_class = WeightMeasurementForm
    template_name = "tracking/add_weight.html"
    success_url = reverse_lazy("weight_history")

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class WeightMeasurementListView(LoginRequiredMixin, ListView):
    model = WeightMeasurement
    template_name = "tracking/weight_list.html"
    context_object_name = "weight_measurements"
    paginate_by = 20

    def get_queryset(self):
        return WeightMeasurement.objects.filter(user=self.request.user).order_by("-date", "-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        measurements = list(context["weight_measurements"])

        for i, measurement in enumerate(measurements):
            measurement.peso_perdido = 0
            measurement.porcentaje = 0
            if i + 1 < len(measurements):
                prev_measurement = measurements[i + 1]
                perdido = prev_measurement.weight - measurement.weight
                measurement.peso_perdido = perdido
                if prev_measurement.weight > 0:
                    measurement.porcentaje = (perdido / prev_measurement.weight) * 100

        all_measurements = WeightMeasurement.objects.filter(user=self.request.user).order_by("date", "created_at")
        first_measurement = all_measurements.first()
        last_measurement = all_measurements.last()

        total_weight_diff = 0
        total_weight_diff_pct = 0

        if first_measurement and last_measurement and first_measurement != last_measurement:
            perdido = first_measurement.weight - last_measurement.weight
            total_weight_diff = perdido
            if first_measurement.weight > 0:
                total_weight_diff_pct = (perdido / first_measurement.weight) * 100

        context["total_weight_diff"] = total_weight_diff
        context["total_weight_diff_pct"] = total_weight_diff_pct
        context["last_weight"] = last_measurement.weight if last_measurement else None

        return context


# ── Suplementos ──────────────────────────────────────────────────────────────

class SupplementListView(LoginRequiredMixin, ListView):
    model = Supplement
    template_name = "tracking/supplements.html"
    context_object_name = "supplements"

    def get_queryset(self):
        return Supplement.objects.filter(user=self.request.user)


class SupplementCreateView(LoginRequiredMixin, CreateView):
    model = Supplement
    form_class = SupplementForm
    template_name = "tracking/supplement_form.html"
    success_url = reverse_lazy("supplement_list")

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class SupplementLogCreateView(LoginRequiredMixin, CreateView):
    model = SupplementLog
    form_class = SupplementLogForm
    template_name = "tracking/supplement_log_form.html"
    success_url = reverse_lazy("supplement_log_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class SupplementLogListView(LoginRequiredMixin, ListView):
    model = SupplementLog
    template_name = "tracking/supplement_log_list.html"
    context_object_name = "logs"
    paginate_by = 30

    def get_queryset(self):
        return SupplementLog.objects.filter(user=self.request.user).select_related("supplement")


# ── Actividades Físicas ───────────────────────────────────────────────────────

class PhysicalActivityListView(LoginRequiredMixin, ListView):
    model = PhysicalActivity
    template_name = "tracking/activities.html"
    context_object_name = "activities"

    def get_queryset(self):
        return PhysicalActivity.objects.filter(user=self.request.user)


class PhysicalActivityCreateView(LoginRequiredMixin, CreateView):
    model = PhysicalActivity
    form_class = PhysicalActivityForm
    template_name = "tracking/activity_form.html"
    success_url = reverse_lazy("activity_list")

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class PhysicalActivityLogListView(LoginRequiredMixin, ListView):
    model = PhysicalActivityLog
    template_name = "tracking/activity_log_list.html"
    context_object_name = "activity_logs"
    paginate_by = 30

    def get_queryset(self):
        return PhysicalActivityLog.objects.filter(user=self.request.user).select_related("activity")


class PhysicalActivityLogCreateView(LoginRequiredMixin, CreateView):
    model = PhysicalActivityLog
    form_class = PhysicalActivityLogForm
    template_name = "tracking/activity_log_form.html"
    success_url = reverse_lazy("activity_log_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


# ── Alimentación ──────────────────────────────────────────────────────────────

class FoodLogListView(LoginRequiredMixin, ListView):
    model = FoodLog
    template_name = "tracking/food_log_list.html"
    context_object_name = "food_logs"
    paginate_by = 30

    def get_queryset(self):
        return FoodLog.objects.filter(user=self.request.user).order_by("-date", "-id")


class FoodLogCreateView(LoginRequiredMixin, CreateView):
    model = FoodLog
    form_class = FoodLogForm
    template_name = "tracking/food_log_form.html"
    success_url = reverse_lazy("food_daily_history")

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        from .forms import FoodLogItemFormSet
        if self.request.POST:
            data['items'] = FoodLogItemFormSet(self.request.POST, form_kwargs={'user': self.request.user})
        else:
            data['items'] = FoodLogItemFormSet(form_kwargs={'user': self.request.user})
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        items = context['items']
        with transaction.atomic():
            form.instance.user = self.request.user
            self.object = form.save()
            if items.is_valid():
                items.instance = self.object
                items.save()
            else:
                return self.form_invalid(form)
        return super().form_valid(form)

class FoodLogUpdateView(LoginRequiredMixin, UpdateView):
    model = FoodLog
    form_class = FoodLogForm
    template_name = "tracking/food_log_form.html"
    success_url = reverse_lazy("food_daily_history")

    def get_queryset(self):
        return FoodLog.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        from .forms import FoodLogItemFormSet
        if self.request.POST:
            data['items'] = FoodLogItemFormSet(self.request.POST, instance=self.object, form_kwargs={'user': self.request.user})
        else:
            data['items'] = FoodLogItemFormSet(instance=self.object, form_kwargs={'user': self.request.user})
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        items = context['items']
        with transaction.atomic():
            self.object = form.save()
            if items.is_valid():
                items.instance = self.object
                items.save()
            else:
                return self.form_invalid(form)
        return super().form_valid(form)


class DailyFoodLogHistoryView(LoginRequiredMixin, ListView):
    template_name = "tracking/food_daily_history.html"
    context_object_name = "daily_food_data"
    paginate_by = 20

    def get_queryset(self):
        # Primero obtenemos las fechas distintas
        dates = FoodLog.objects.filter(user=self.request.user).values_list('date', flat=True).distinct().order_by('-date')
        return dates

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        paginated_dates = context.get('daily_food_data', [])
        
        # Recuperar todos los registros para las fechas paginadas
        food_logs = FoodLog.objects.filter(
            user=self.request.user, 
            date__in=paginated_dates
        ).prefetch_related('items__food', 'items__recipe')
        
        grouped_data = []
        for d in paginated_dates:
            logs_for_date = [log for log in food_logs if log.date == d]
            daily_totals = {
                "calories": 0.0,
                "proteins": 0.0,
                "lipids": 0.0,
                "carbs": 0.0,
            }
            for log in logs_for_date:
                macros = log.get_nutritional_totals()
                for key in daily_totals:
                    daily_totals[key] += macros[key]
            
            grouped_data.append({
                "date": d,
                "totals": daily_totals,
                "log_count": len(logs_for_date)
            })
            
        context['daily_food_data'] = grouped_data
        return context


class DailyFoodLogDetailView(LoginRequiredMixin, TemplateView):
    template_name = "tracking/partials/daily_food_modal.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        date_str = self.kwargs.get('date')
        logs = FoodLog.objects.filter(
            user=self.request.user,
            date=date_str
        ).prefetch_related('items__food', 'items__recipe').order_by('id')
        
        context['food_logs'] = logs
        context['date_str'] = date_str
        return context


# ── Análisis y Dashboard Cruzado ──────────────────────────────────────────────

class AnalysisView(LoginRequiredMixin, TemplateView):
    template_name = "tracking/analysis.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        thirty_days_ago = timezone.now().date() - timedelta(days=30)

        sessions = list(MeasurementSession.objects.filter(user=user, date__gte=thirty_days_ago).order_by("date"))
        weights = list(WeightMeasurement.objects.filter(user=user, date__gte=thirty_days_ago).order_by("date"))
        activities = list(PhysicalActivityLog.objects.filter(user=user, date__gte=thirty_days_ago).order_by("date").select_related("activity"))
        daily_activities = list(DailyActivityLog.objects.filter(user=user, date__gte=thirty_days_ago).order_by("date"))

        # Prefetch all food data in 2 queries total
        foods = list(
            FoodLog.objects.filter(user=user, date__gte=thirty_days_ago)
            .prefetch_related("items__food", "items__recipe__ingredients__food")
            .order_by("date")
        )
        # Precompute nutrition for all recipes used in this period
        from nutrition.models import Recipe
        recipe_ids = set()
        for f in foods:
            for item in f.items.all():
                if item.recipe_id:
                    recipe_ids.add(item.recipe_id)
        recipe_cache = {}
        if recipe_ids:
            for recipe in Recipe.objects.filter(id__in=recipe_ids).prefetch_related("ingredients__food"):
                recipe_cache[recipe.id] = recipe

        # Group food logs by date for O(1) lookups
        foods_by_date = {}
        for f in foods:
            foods_by_date.setdefault(f.date, []).append(f)

        dates_set = set()
        for obj in sessions + weights + activities + daily_activities + foods:
            dates_set.add(obj.date)

        sorted_dates = sorted(dates_set)

        MICRO_FIELDS = [
            "cholesterol_mg", "fiber_g", "calcium_mg", "iron_mg", "iodine_ug",
            "magnesium_mg", "zinc_mg", "sodium_mg", "potassium_mg", "phosphorus_mg",
            "selenium_ug", "thiamine_mg", "riboflavin_mg", "vitamin_b6_mg",
            "folate_ug", "vitamin_b12_ug", "vitamin_c_mg", "vitamin_a_ug",
            "vitamin_d_ug", "vitamin_e_mg",
        ]

        daily_data = []
        for d in sorted_dates:
            d_sessions = [s for s in sessions if s.date == d]
            d_weights = [w for w in weights if w.date == d]
            d_acts = [a for a in activities if a.date == d]
            d_foods = foods_by_date.get(d, [])
            d_daily_acts = [da for da in daily_activities if da.date == d]

            daily_nutrition = {field: 0.0 for field in [
                "energy_kcal", "proteins_g", "lipids_g", "cholesterol_mg", "carbohydrates_g",
                "fiber_g", "calcium_mg", "iron_mg", "iodine_ug", "magnesium_mg", "zinc_mg",
                "sodium_mg", "potassium_mg", "phosphorus_mg", "selenium_ug", "thiamine_mg",
                "riboflavin_mg", "vitamin_b6_mg", "folate_ug", "vitamin_b12_ug", "vitamin_c_mg",
                "vitamin_a_ug", "vitamin_d_ug", "vitamin_e_mg"
            ]}

            for food_log in d_foods:
                totals = food_log.get_nutritional_totals()
                daily_nutrition["energy_kcal"] += totals.get("calories", 0)
                daily_nutrition["proteins_g"] += totals.get("proteins", 0)
                daily_nutrition["lipids_g"] += totals.get("lipids", 0)
                daily_nutrition["carbohydrates_g"] += totals.get("carbs", 0)

                for item in food_log.items.all():
                    if item.food and item.quantity_g is not None:
                        factor = float(item.quantity_g) / 100.0
                        for field in MICRO_FIELDS:
                            daily_nutrition[field] += float(getattr(item.food, field) or 0) * factor
                    elif item.recipe and item.servings is not None:
                        recipe = recipe_cache.get(item.recipe_id)
                        if recipe:
                            factor = float(item.servings) / float(recipe.servings) if recipe.servings else float(item.servings)
                            rec_nut = recipe.calculate_nutrition()
                            for field in MICRO_FIELDS:
                                daily_nutrition[field] += float(rec_nut.get(field, 0) or 0) * factor

            if d_daily_acts:
                da = d_daily_acts[0]
                resting_c = da.resting_calories
                active_c = da.active_calories
                steps_c = da.steps
                dist_c = float(da.distance_km)
                extra_exercise_c = da.extra_exercise_calories
                total_burned = da.get_total_calories_burned()
            else:
                w_val = 70.0
                w_meas = [w for w in weights if w.date <= d]
                if w_meas:
                    w_val = float(w_meas[-1].weight)
                elif weights:
                    w_val = float(weights[0].weight)

                resting_c = user.calculate_bmr(w_val)
                active_c = 0
                steps_c = 0
                dist_c = 0.0
                extra_exercise_c = sum(log.estimated_calories or 0 for log in d_acts if log.not_tracked_by_watch)
                total_burned = resting_c + active_c + extra_exercise_c

            total_intake = daily_nutrition["energy_kcal"]
            caloric_balance = total_intake - total_burned

            daily_data.append({
                "date": d,
                "sessions": d_sessions,
                "weight": d_weights[-1] if d_weights else None,
                "activities": d_acts,
                "foods": d_foods,
                "daily_nutrition": daily_nutrition,
                "steps": steps_c,
                "balance": caloric_balance,
                "intake": total_intake,
                "expenditure": total_burned,
                "avg_sys": sum(s.avg_systolic for s in d_sessions if s.avg_systolic) / len(d_sessions) if d_sessions and any(s.avg_systolic for s in d_sessions) else None,
                "avg_dia": sum(s.avg_diastolic for s in d_sessions if s.avg_diastolic) / len(d_sessions) if d_sessions and any(s.avg_diastolic for s in d_sessions) else None,
            })

        context["daily_data"] = daily_data
        context["chart_labels"] = json.dumps([d["date"].strftime("%d/%m") for d in daily_data])
        
        # Extract arrays for chartjs
        sys_data = [d["avg_sys"] for d in daily_data]
        dia_data = [d["avg_dia"] for d in daily_data]
        weight_data = [float(d["weight"].weight) if d["weight"] else None for d in daily_data]
        
        steps_data = [d["steps"] for d in daily_data]
        balance_data = [d["balance"] for d in daily_data]
        intake_data = [d["intake"] for d in daily_data]
        expenditure_data = [d["expenditure"] for d in daily_data]

        context["sys_data"] = json.dumps(sys_data)
        context["dia_data"] = json.dumps(dia_data)
        context["weight_data"] = json.dumps(weight_data)
        context["steps_data"] = json.dumps(steps_data)
        context["balance_data"] = json.dumps(balance_data)
        context["intake_data"] = json.dumps(intake_data)
        context["expenditure_data"] = json.dumps(expenditure_data)
        
        # Generar referencias nutricionales serializadas
        nut_refs = NutritionalReference.objects.all()
        ref_dict = {}
        for r in nut_refs:
            ref_dict[r.gender] = {
                field: float(getattr(r, field) or 0)
                for field in [
                    "energy_kcal", "proteins_g", "lipids_g", "cholesterol_mg", "carbohydrates_g",
                    "fiber_g", "calcium_mg", "iron_mg", "iodine_ug", "magnesium_mg", "zinc_mg",
                    "sodium_mg", "potassium_mg", "phosphorus_mg", "selenium_ug", "thiamine_mg",
                    "riboflavin_mg", "vitamin_b6_mg", "folate_ug", "vitamin_b12_ug", "vitamin_c_mg",
                    "vitamin_a_ug", "vitamin_d_ug", "vitamin_e_mg"
                ]
            }
        context["nutritional_references"] = json.dumps(ref_dict)

        # AI Insights
        from tracking.services.ai_analysis import generate_insights
        ai_data = generate_insights(user)
        context["ai_insights"] = ai_data.get("insights", [])
        context["timeline_labels"] = json.dumps(ai_data.get("timeline_labels", []))
        context["ai_weight_data"] = json.dumps(ai_data.get("weight_data", []))
        context["sport_data"] = json.dumps(ai_data.get("sport_data", []))

        return context


# ── Actividad Diaria (Apple Watch) ───────────────────────────────────────────

class DailyActivityLogListView(LoginRequiredMixin, ListView):
    model = DailyActivityLog
    template_name = "tracking/daily_activity_list.html"
    context_object_name = "daily_activities"
    paginate_by = 30

    def get_queryset(self):
        return DailyActivityLog.objects.filter(user=self.request.user).order_by("-date")


class DailyActivityLogCreateView(LoginRequiredMixin, CreateView):
    model = DailyActivityLog
    form_class = DailyActivityLogForm
    template_name = "tracking/daily_activity_form.html"
    success_url = reverse_lazy("daily_activity_list")

    def form_valid(self, form):
        form.instance.user = self.request.user
        if not form.instance.resting_calories or form.instance.resting_calories == 0:
            bmr, _ = get_bmr_for_user(self.request.user, date=form.instance.date)
            form.instance.resting_calories = bmr
        return super().form_valid(form)


class DailyActivityLogUpdateView(LoginRequiredMixin, UpdateView):
    model = DailyActivityLog
    form_class = DailyActivityLogForm
    template_name = "tracking/daily_activity_form.html"
    success_url = reverse_lazy("daily_activity_list")

    def get_queryset(self):
        return DailyActivityLog.objects.filter(user=self.request.user)

    def form_valid(self, form):
        if not form.instance.resting_calories or form.instance.resting_calories == 0:
            bmr, _ = get_bmr_for_user(self.request.user, date=form.instance.date)
            form.instance.resting_calories = bmr
        return super().form_valid(form)


class ExportDataCSVView(LoginRequiredMixin, View):
    def get(self, request):
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = "attachment; filename=tension_export.csv"
        writer = csv.writer(response)
        writer.writerow(["Fecha", "Tipo", "Sistólica", "Diastólica", "Pulsaciones",
                         "Peso(kg)", "MasaMagra(kg)", "MasaGrasa(kg)",
                         "CaloríasIngeridas", "CaloríasActivas", "Pasos"])

        sessions = MeasurementSession.objects.filter(user=request.user).order_by("-date")
        weights = {w.date: w for w in WeightMeasurement.objects.filter(user=request.user).order_by("-date")}
        daily_logs = {d.date: d for d in DailyActivityLog.objects.filter(user=request.user).order_by("-date")}

        for s in sessions:
            w = weights.get(s.date)
            d = daily_logs.get(s.date)
            writer.writerow([
                s.date, s.get_session_type_display(),
                s.avg_systolic, s.avg_diastolic, s.avg_pulse,
                float(w.weight) if w else "",
                float(w.lean_mass_kg) if w and w.lean_mass_kg else "",
                float(w.fat_mass_kg) if w and w.fat_mass_kg else "",
                "", "", ""
            ])

        return response

