"""URLconf de recetas.egalvez.es.

Sirve la app ``recipes`` en la raíz del subdominio, con autenticación
compartida (SSO) y endpoints de alimentos accesibles en el mismo origen.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import TemplateView

from nutrition import views as nutrition_views

urlpatterns = [
    path("", include("recipes.urls")),
    # API de alimentos en el mismo origen (para el editor de recetas)
    path("api/foods/create/", nutrition_views.QuickFoodCreateAPIView.as_view(), name="api_food_create"),
    path("api/foods/search/", nutrition_views.FoodSearchAPIView.as_view(), name="api_food_search"),
    # Autenticación (con redirección a la portada de recetas, no a dashboard de tensión)
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(
            template_name="recipes/login.html",
            next_page="recipe_list",
        ),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(next_page="recipe_list"), name="logout"),
    path("accounts/", include("django.contrib.auth.urls")),
    path(
        "robots.txt",
        TemplateView.as_view(template_name="recetas/robots.txt", content_type="text/plain"),
        name="recetas_robots",
    ),
]

# En desarrollo Django sirve los ficheros subidos; en producción lo hace Nginx.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
