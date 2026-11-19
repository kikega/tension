"""Middleware de enrutado por dominio.

Un mismo proyecto Django sirve varias webs (tension.egalvez.es y
recetas.egalvez.es). Según el host de la petición se asigna un urlconf
distinto mediante ``request.urlconf``; si el host no está mapeado en
``settings.HOST_URLCONFS`` se usa ``ROOT_URLCONF`` (tensión).
"""

from django.conf import settings
from django.http.request import split_domain_port


class HostRoutingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.host_urlconfs = {
            host.lower(): urlconf for host, urlconf in getattr(settings, "HOST_URLCONFS", {}).items()
        }

    def __call__(self, request):
        # get_host() valida contra ALLOWED_HOSTS (lanza DisallowedHost si no es válido).
        domain, _port = split_domain_port(request.get_host())
        urlconf = self.host_urlconfs.get(domain)
        if urlconf:
            request.urlconf = urlconf
        return self.get_response(request)
