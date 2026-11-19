from django.http import HttpResponsePermanentRedirect
from django.urls import path

from core.sites import build_site_url
from recipes import views as recipe_views

from . import views


def _redirect_to_recetas(url_name: str):
    """Devuelve una vista que redirige 301 de tension.egalvez.es/nutrition/recipes/... a recetas.egalvez.es."""

    def view(request, **kwargs):
        target = build_site_url("recetas", url_name, request=request, kwargs=kwargs or None)
        query = request.META.get("QUERY_STRING")
        if query:
            target = f"{target}?{query}"
        return HttpResponsePermanentRedirect(target)

    return view


urlpatterns = [
    # Alimentos (base común gestionada desde tensión)
    path("foods/", views.FoodListView.as_view(), name="food_list"),
    path("foods/add/", views.FoodCreateView.as_view(), name="food_add"),
    path("foods/<int:pk>/", views.FoodDetailView.as_view(), name="food_detail"),
    path("foods/<int:pk>/edit/", views.FoodUpdateView.as_view(), name="food_edit"),
    path("foods/<int:pk>/delete/", views.FoodDeleteView.as_view(), name="food_delete"),
    # Recetas: redirecciones permanentes 301 al subdominio recetas.egalvez.es
    path("recipes/", _redirect_to_recetas("recipe_list"), name="recipe_list"),
    path("recipes/add/", _redirect_to_recetas("recipe_add"), name="recipe_add"),
    path("recipes/<int:pk>/", _redirect_to_recetas("recipe_detail"), name="recipe_detail"),
    path("recipes/<int:pk>/edit/", _redirect_to_recetas("recipe_edit"), name="recipe_edit"),
    path("recipes/<int:pk>/delete/", _redirect_to_recetas("recipe_delete"), name="recipe_delete"),
    # API endpoints para creación y consulta al vuelo (mismo origen para food_log_form)
    path("api/foods/create/", views.QuickFoodCreateAPIView.as_view(), name="api_food_create"),
    path("api/foods/search/", views.FoodSearchAPIView.as_view(), name="api_food_search"),
    path("api/recipes/create/", recipe_views.QuickRecipeCreateAPIView.as_view(), name="api_recipe_create"),
    path("api/recipes/<int:pk>/detail/", recipe_views.RecipeDetailAPIView.as_view(), name="api_recipe_detail"),
]
