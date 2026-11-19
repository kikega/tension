"""Tests del enrutado por dominio, redirecciones 301 y configuración de media."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

HOSTS = ["tension.egalvez.es", "recetas.egalvez.es", "recetas.localhost", "localhost", "testserver"]
User = get_user_model()


@override_settings(ALLOWED_HOSTS=HOSTS)
class HostRoutingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="host@example.com", password="password123")

    def test_recetas_host_anonimo_redirige_a_login_propio(self):
        response = self.client.get("/", HTTP_HOST="recetas.egalvez.es")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

        login_resp = self.client.get("/accounts/login/", HTTP_HOST="recetas.egalvez.es")
        self.assertEqual(login_resp.status_code, 200)
        self.assertTemplateUsed(login_resp, "recipes/login.html")

    def test_recetas_host_autenticado_sirve_listado_recetas(self):
        self.client.force_login(self.user)
        response = self.client.get("/", HTTP_HOST="recetas.egalvez.es")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "recipes/recipe_list.html")
        self.assertTemplateUsed(response, "recipes/base.html")

    def test_recetas_host_con_puerto(self):
        self.client.force_login(self.user)
        response = self.client.get("/", HTTP_HOST="recetas.localhost:8000")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "recipes/recipe_list.html")

    def test_recetas_robots_bloquea_indexacion(self):
        response = self.client.get("/robots.txt", HTTP_HOST="recetas.egalvez.es")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain")
        self.assertContains(response, "Disallow: /")

    def test_recetas_no_expone_rutas_de_tension(self):
        response = self.client.get("/nutrition/recipes/", HTTP_HOST="recetas.egalvez.es")
        self.assertEqual(response.status_code, 404)

    def test_tension_host_mantiene_su_urlconf(self):
        response = self.client.get("/", HTTP_HOST="tension.egalvez.es")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_tension_redirige_301_rutas_antiguas_de_recetas(self):
        cases = [
            ("/nutrition/recipes/", "https://recetas.egalvez.es/"),
            ("/nutrition/recipes/?page=2", "https://recetas.egalvez.es/?page=2"),
            ("/nutrition/recipes/add/", "https://recetas.egalvez.es/add/"),
            ("/nutrition/recipes/42/", "https://recetas.egalvez.es/42/"),
            ("/nutrition/recipes/42/edit/", "https://recetas.egalvez.es/42/edit/"),
            ("/nutrition/recipes/42/delete/", "https://recetas.egalvez.es/42/delete/"),
        ]
        for old_path, expected in cases:
            with self.subTest(old_path=old_path):
                resp = self.client.get(old_path, HTTP_HOST="tension.egalvez.es", secure=True)
                self.assertEqual(resp.status_code, 301)
                self.assertEqual(resp["Location"], expected)

    def test_tension_local_redirige_a_recetas_localhost_con_puerto(self):
        resp = self.client.get("/nutrition/recipes/7/", HTTP_HOST="localhost:8000")
        self.assertEqual(resp.status_code, 301)
        self.assertEqual(resp["Location"], "http://recetas.localhost:8000/7/")

    def test_host_no_mapeado_usa_root_urlconf(self):
        response = self.client.get("/accounts/login/", HTTP_HOST="testserver")
        self.assertEqual(response.status_code, 200)


class MediaSettingsTests(TestCase):
    def test_media_configurado(self):
        self.assertEqual(settings.MEDIA_URL, "/media/")
        self.assertTrue(str(settings.MEDIA_ROOT))
        self.assertEqual(settings.FILE_UPLOAD_PERMISSIONS, 0o644)
