"""URLconf de recetas.egalvez.es.

Fase 0: solo página "próximamente". En la Fase 1 se conectarán aquí las
vistas de la app de recetas.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from django.views.generic import TemplateView

urlpatterns = [
    path(
        "",
        TemplateView.as_view(
            template_name="recetas/proximamente.html",
            extra_context={"tension_host": settings.TENSION_HOST},
        ),
        name="recetas_home",
    ),
    path(
        "robots.txt",
        TemplateView.as_view(template_name="recetas/robots.txt", content_type="text/plain"),
        name="recetas_robots",
    ),
]

# En desarrollo Django sirve los ficheros subidos; en producción lo hace Nginx.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
