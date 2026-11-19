"""Utilidades para construir URLs entre subdominios (tensión ↔ recetas)."""

from django.conf import settings
from django.http.request import split_domain_port
from django.urls import reverse

LOCAL_HOSTS = {"localhost", "127.0.0.1", "recetas.localhost", "testserver"}


def get_site_base_url(site: str, request=None) -> str:
    """Devuelve la URL base (esquema + host[:puerto]) para 'tension' o 'recetas'.

    En desarrollo local (cuando el host de la petición es localhost/127.0.0.1/
    recetas.localhost) conserva el esquema y el puerto y alterna entre
    ``localhost`` y ``recetas.localhost``. En producción usa ``https://`` con
    ``TENSION_HOST`` / ``RECETAS_HOST``.
    """
    if site == "recetas":
        prod_host = settings.RECETAS_HOST
        local_host = "recetas.localhost"
    elif site == "tension":
        prod_host = settings.TENSION_HOST
        local_host = "localhost"
    else:
        raise ValueError(f"Sitio desconocido: {site!r}")

    if request is not None:
        raw_host = request.get_host()
        domain, port = split_domain_port(raw_host)
        scheme = "https" if request.is_secure() else "http"
        if domain in LOCAL_HOSTS:
            host = f"{local_host}:{port}" if port else local_host
            return f"{scheme}://{host}"
        if port and port not in ("80", "443"):
            return f"{scheme}://{prod_host}:{port}"
        return f"{scheme}://{prod_host}"

    return f"https://{prod_host}"


def build_site_url(site: str, url_name: str, request=None, args=None, kwargs=None) -> str:
    """Resuelve ``url_name`` en el urlconf del sitio destino y devuelve la URL absoluta."""
    urlconf = "config.urls_recetas" if site == "recetas" else "config.urls"
    path = reverse(url_name, urlconf=urlconf, args=args, kwargs=kwargs)
    return f"{get_site_base_url(site, request=request)}{path}"
