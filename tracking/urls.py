from django.urls import path
from . import views

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('add/', views.AddMeasurementView.as_view(), name='add_measurement'),
    path('history/', views.HistoryListView.as_view(), name='history'),
    path('weight/add/', views.WeightMeasurementCreateView.as_view(), name='add_weight'),
    path('weight/history/', views.WeightMeasurementListView.as_view(), name='weight_history'),
]
