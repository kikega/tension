from django.contrib import admin
from .models import MeasurementSession, MeasurementReading

class ReadingInline(admin.TabularInline):
    model = MeasurementReading
    extra = 3
    min_num = 3
    max_num = 3

@admin.register(MeasurementSession)
class MeasurementSessionAdmin(admin.ModelAdmin):
    list_display = ('date', 'time_of_day', 'session_type', 'avg_systolic', 'avg_diastolic', 'mood')
    list_filter = ('session_type', 'time_of_day', 'mood')
    inlines = [ReadingInline]
    
    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        # Recalculate averages after saving inline readings
        form.instance.calculate_averages()

@admin.register(MeasurementReading)
class MeasurementReadingAdmin(admin.ModelAdmin):
    list_display = ('session', 'order', 'systolic', 'diastolic', 'pulse')
