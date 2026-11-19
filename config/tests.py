"""Tests del enrutado por dominio (Fase 0)."""

from django.conf import settings
from django.test import TestCase, override_settings

HOSTS = ["tension.egalvez.es", "recetas.egalvez.es", "recetas.localhost", "testserver"]


@override_settings(ALLOWED_HOSTS=HOSTS)
class HostRoutingTests(TestCase):
    def test_recetas_host_sirve_pagina_proximamente(self):
        response = self.client.get("/", HTTP_HOST="recetas.egalvez.es")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "recetas/proximamente.html")
        self.assertContains(response, "noindex")
        self.assertContains(response, f"https://{settings.TENSION_HOST}/")

    def test_recetas_host_con_puerto(self):
        response = self.client.get("/", HTTP_HOST="recetas.localhost:8000")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "recetas/proximamente.html")

    def test_recetas_robots_bloquea_indexacion(self):
        response = self.client.get("/robots.txt", HTTP_HOST="recetas.egalvez.es")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain")
        self.assertContains(response, "Disallow: /")

    def test_recetas_no_expone_rutas_de_tension(self):
        response = self.client.get("/nutrition/recipes/", HTTP_HOST="recetas.egalvez.es")
        self.assertEqual(response.status_code, 404)

    def test_tension_host_mantiene_su_urlconf(self):
        # El dashboard exige login: debe redirigir, no mostrar "próximamente".
        response = self.client.get("/", HTTP_HOST="tension.egalvez.es")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_host_no_mapeado_usa_root_urlconf(self):
        response = self.client.get("/accounts/login/", HTTP_HOST="testserver")
        self.assertEqual(response.status_code, 200)


class MediaSettingsTests(TestCase):
    def test_media_configurado(self):
        self.assertEqual(settings.MEDIA_URL, "/media/")
        self.assertTrue(str(settings.MEDIA_ROOT))
        self.assertEqual(settings.FILE_UPLOAD_PERMISSIONS, 0o644)
