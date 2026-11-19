"""Template tags para enlazar entre tension.egalvez.es y recetas.egalvez.es."""

from django import template

from core.sites import build_site_url

register = template.Library()


@register.simple_tag(takes_context=True)
def tension_url(context, url_name, *args, **kwargs):
    return build_site_url("tension", url_name, request=context.get("request"), args=args or None, kwargs=kwargs or None)


@register.simple_tag(takes_context=True)
def recetas_url(context, url_name, *args, **kwargs):
    return build_site_url("recetas", url_name, request=context.get("request"), args=args or None, kwargs=kwargs or None)
