from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, CreateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.db import transaction
from django.core.serializers.json import DjangoJSONEncoder
import json       

from .models import MeasurementSession, WeightMeasurement
from .forms import MeasurementSessionForm, ReadingFormSet, WeightMeasurementForm

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "tracking/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # --- Blood Pressure & Pulse Data ---
        sessions = MeasurementSession.objects.filter(user=self.request.user).order_by('-date', '-created_at')
        context['recent_sessions'] = sessions[:10]
        
        last_30_sessions = sessions[:30] 
        chart_sessions = list(reversed(last_30_sessions))
        dates = [s.date.strftime("%d/%m") for s in chart_sessions]
        bp_data = [[s.avg_diastolic, s.avg_systolic] for s in chart_sessions]
        pulse_data = [s.avg_pulse for s in chart_sessions]
        
        context['chart_labels'] = json.dumps(dates)
        context['bp_data'] = json.dumps(bp_data) 
        context['pulse_data'] = json.dumps(pulse_data)

        # --- Weight Data ---
        weights = WeightMeasurement.objects.filter(user=self.request.user).order_by('-date', '-created_at')
        last_10_weights = list(reversed(weights[:10]))
        weight_dates = [w.date.strftime("%d/%m") for w in last_10_weights]
        weight_values = [float(w.weight) for w in last_10_weights]
        
        context['weight_labels'] = json.dumps(weight_dates)
        context['weight_data'] = json.dumps(weight_values)
        
        return context

class AddMeasurementView(LoginRequiredMixin, CreateView):
    model = MeasurementSession
    form_class = MeasurementSessionForm
    template_name = "tracking/add_measurement.html"
    success_url = reverse_lazy('dashboard')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['readings'] = ReadingFormSet(self.request.POST)
        else:
            context['readings'] = ReadingFormSet()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        readings = context['readings']
        with transaction.atomic():
            form.instance.user = self.request.user
            self.object = form.save()
            if readings.is_valid():
                readings.instance = self.object
                readings.save()
                self.object.calculate_averages()
            else:
                return self.form_invalid(form)
        return super().form_valid(form)

class HistoryListView(LoginRequiredMixin, ListView):
    model = MeasurementSession
    template_name = "tracking/history.html"
    context_object_name = "sessions"
    paginate_by = 20

    def get_queryset(self):
        qs = MeasurementSession.objects.filter(user=self.request.user)
        session_type = self.request.GET.get('type')
        if session_type:
            qs = qs.filter(session_type=session_type)
        return qs.order_by('-date', '-created_at')

class WeightMeasurementCreateView(LoginRequiredMixin, CreateView):
    model = WeightMeasurement
    form_class = WeightMeasurementForm
    template_name = "tracking/add_weight.html"
    success_url = reverse_lazy('weight_history')

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

class WeightMeasurementListView(LoginRequiredMixin, ListView):
    model = WeightMeasurement
    template_name = "tracking/weight_list.html"
    context_object_name = "weight_measurements"
    paginate_by = 20

    def get_queryset(self):
        return WeightMeasurement.objects.filter(user=self.request.user).order_by('-date', '-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        measurements = list(context['weight_measurements'])
        
        # Calculate weight loss compared to the previous measurement (which is the next item in the list since it's ordered by -date)
        for i, measurement in enumerate(measurements):
            measurement.peso_perdido = 0
            measurement.porcentaje = 0
            
            # The "previous" measurement in time is the next one in the reversed list
            if i + 1 < len(measurements):
                prev_measurement = measurements[i + 1]
                # If you weighed 80 yesterday and 79 today, peso_perdido = 1.0
                perdido = prev_measurement.weight - measurement.weight
                measurement.peso_perdido = perdido
                if prev_measurement.weight > 0:
                    measurement.porcentaje = (perdido / prev_measurement.weight) * 100

        # Calculate total weight loss
        all_measurements = WeightMeasurement.objects.filter(user=self.request.user).order_by('date', 'created_at')
        first_measurement = all_measurements.first()
        last_measurement = all_measurements.last()
        
        total_weight_diff = 0
        total_weight_diff_pct = 0
        
        if first_measurement and last_measurement and first_measurement != last_measurement:
            # Note: last_measurement is the most recent because order_by is ascending 'date'
            perdido = first_measurement.weight - last_measurement.weight
            total_weight_diff = perdido
            if first_measurement.weight > 0:
                total_weight_diff_pct = (perdido / first_measurement.weight) * 100
                
        context['total_weight_diff'] = total_weight_diff
        context['total_weight_diff_pct'] = total_weight_diff_pct
        
        return context
