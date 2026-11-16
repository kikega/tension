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
    path("weight/<int:pk>/edit/", views.WeightMeasurementUpdateView.as_view(), name="weight_edit"),
    path("weight/<int:pk>/delete/", views.WeightMeasurementDeleteView.as_view(), name="weight_delete"),
    # Suplementos
    path("supplements/", views.SupplementListView.as_view(), name="supplement_list"),
    path("supplements/add/", views.SupplementCreateView.as_view(), name="supplement_add"),
    path("supplements/<int:pk>/edit/", views.SupplementUpdateView.as_view(), name="supplement_edit"),
    path("supplements/<int:pk>/delete/", views.SupplementDeleteView.as_view(), name="supplement_delete"),
    path("supplements/log/", views.SupplementLogListView.as_view(), name="supplement_log_list"),
    path("supplements/log/add/", views.SupplementLogCreateView.as_view(), name="supplement_log_add"),
    path("supplements/log/<int:pk>/edit/", views.SupplementLogUpdateView.as_view(), name="supplement_log_edit"),
    path("supplements/log/<int:pk>/delete/", views.SupplementLogDeleteView.as_view(), name="supplement_log_delete"),
    # Actividades Físicas
    path("activities/", views.PhysicalActivityListView.as_view(), name="activity_list"),
    path("activities/add/", views.PhysicalActivityCreateView.as_view(), name="activity_add"),
    path("activities/<int:pk>/edit/", views.PhysicalActivityUpdateView.as_view(), name="activity_edit"),
    path("activities/<int:pk>/delete/", views.PhysicalActivityDeleteView.as_view(), name="activity_delete"),
    path("activities/log/", views.PhysicalActivityLogListView.as_view(), name="activity_log_list"),
    path("activities/log/add/", views.PhysicalActivityLogCreateView.as_view(), name="activity_log_add"),
    path("activities/log/<int:pk>/edit/", views.PhysicalActivityLogUpdateView.as_view(), name="activity_log_edit"),
    path("activities/log/<int:pk>/delete/", views.PhysicalActivityLogDeleteView.as_view(), name="activity_log_delete"),
    # Actividad Diaria (Apple Watch)
    path("daily-activity/", views.DailyActivityLogListView.as_view(), name="daily_activity_list"),
    path("daily-activity/add/", views.DailyActivityLogCreateView.as_view(), name="daily_activity_add"),
    path("daily-activity/<int:pk>/edit/", views.DailyActivityLogUpdateView.as_view(), name="daily_activity_edit"),
    # Alimentación
    path("food/", views.FoodLogListView.as_view(), name="food_log_list"),
    path("food/add/", views.FoodLogCreateView.as_view(), name="food_log_add"),
    path("food/<int:pk>/edit/", views.FoodLogUpdateView.as_view(), name="food_log_edit"),
    path("food/<int:pk>/delete/", views.FoodLogDeleteView.as_view(), name="food_log_delete"),
    path("food/history/daily/", views.DailyFoodLogHistoryView.as_view(), name="food_daily_history"),
    path("food/history/daily/<str:date>/", views.DailyFoodLogDetailView.as_view(), name="food_daily_detail"),
    # Análisis
    path("analysis/", views.AnalysisView.as_view(), name="analysis"),
    path("analysis/meal-plan/", views.AnalysisMealPlanPartialView.as_view(), name="analysis_meal_plan_partial"),
    path("analysis/insights/", views.AnalysisInsightsView.as_view(), name="analysis_insights_api"),
    # Exportación
    path("export/csv/", views.ExportDataCSVView.as_view(), name="export_csv"),
]
