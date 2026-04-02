from django.urls import path
from . import views

urlpatterns = [
    # Alimentos
    path("foods/", views.FoodListView.as_view(), name="food_list"),
    path("foods/add/", views.FoodCreateView.as_view(), name="food_add"),
    path("foods/<int:pk>/", views.FoodDetailView.as_view(), name="food_detail"),
    path("foods/<int:pk>/edit/", views.FoodUpdateView.as_view(), name="food_edit"),
    path("foods/<int:pk>/delete/", views.FoodDeleteView.as_view(), name="food_delete"),
    # Recetas
    path("recipes/", views.RecipeListView.as_view(), name="recipe_list"),
    path("recipes/add/", views.RecipeCreateView.as_view(), name="recipe_add"),
    path("recipes/<int:pk>/", views.RecipeDetailView.as_view(), name="recipe_detail"),
    path("recipes/<int:pk>/edit/", views.RecipeUpdateView.as_view(), name="recipe_edit"),
    path("recipes/<int:pk>/delete/", views.RecipeDeleteView.as_view(), name="recipe_delete"),
]
