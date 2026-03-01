from django.urls import path
from . import views

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("add/", views.AddMeasurementView.as_view(), name="add_measurement"),
    path("history/", views.HistoryListView.as_view(), name="history"),
    path("history/print/", views.MeasurementHistoryPrintView.as_view(), name="print_history"),
    path("history/<int:pk>/edit/", views.MeasurementSessionUpdateView.as_view(), name="edit_measurement"),
    # Peso
    path("weight/add/", views.WeightMeasurementCreateView.as_view(), name="add_weight"),
    path("weight/history/", views.WeightMeasurementListView.as_view(), name="weight_history"),
    # Suplementos
    path("supplements/", views.SupplementListView.as_view(), name="supplement_list"),
    path("supplements/add/", views.SupplementCreateView.as_view(), name="supplement_add"),
    path("supplements/log/", views.SupplementLogListView.as_view(), name="supplement_log_list"),
    path("supplements/log/add/", views.SupplementLogCreateView.as_view(), name="supplement_log_add"),
    # Actividades Físicas
    path("activities/", views.PhysicalActivityListView.as_view(), name="activity_list"),
    path("activities/add/", views.PhysicalActivityCreateView.as_view(), name="activity_add"),
]
