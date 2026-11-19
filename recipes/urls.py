from django.urls import path

from . import views

urlpatterns = [
    path("", views.RecipeListView.as_view(), name="recipe_list"),
    path("add/", views.RecipeCreateView.as_view(), name="recipe_add"),
    path("<int:pk>/", views.RecipeDetailView.as_view(), name="recipe_detail"),
    path("<int:pk>/edit/", views.RecipeUpdateView.as_view(), name="recipe_edit"),
    path("<int:pk>/delete/", views.RecipeDeleteView.as_view(), name="recipe_delete"),
    # API endpoints para creación y consulta al vuelo
    path("api/recipes/create/", views.QuickRecipeCreateAPIView.as_view(), name="api_recipe_create"),
    path("api/recipes/<int:pk>/detail/", views.RecipeDetailAPIView.as_view(), name="api_recipe_detail"),
]
