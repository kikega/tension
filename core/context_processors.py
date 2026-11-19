"""Context processors compartidos entre tensión y recetas."""

from .sites import get_site_base_url


def site_urls(request):
    return {
        "TENSION_BASE_URL": get_site_base_url("tension", request=request),
        "RECETAS_BASE_URL": get_site_base_url("recetas", request=request),
    }
