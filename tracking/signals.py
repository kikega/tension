from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import MeasurementReading, MeasurementSession


@receiver([post_save, post_delete], sender=MeasurementReading)
def update_session_averages(sender, instance, **kwargs):
    session = instance.session
    session.calculate_averages()
