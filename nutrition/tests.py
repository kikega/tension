import json
import pytest
from decimal import Decimal
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone

from nutrition.models import Food, FoodCategory, Recipe, RecipeIngredient
from nutrition.services.nutrition_calculator import (
    normalize_nutrients_to_100g,
    scale_nutrients_for_weight,
    calculate_glycemic_load_for_portion,
)
from tracking.models import FoodLog, FoodLogItem

User = get_user_model()


@pytest.fixture
def user_a(db):
    return User.objects.create_user(email="user_a@example.com", password="password")


@pytest.fixture
def user_b(db):
    return User.objects.create_user(email="user_b@example.com", password="password")


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(email="staff@example.com", password="password", is_staff=True)


# ==============================================================================
# 1. PRUEBAS DE SERVICIO CALCULADOR NUTRICIONAL
# ==============================================================================

class TestNutritionCalculatorService:
    def test_normalize_nutrients_to_100g(self):
        """Verifica que los nutrientes de una porción de 150g se escalen a 100g."""
        raw = {
            "energy_kcal": "300.0",
            "proteins_g": "30.0",
            "lipids_g": "15.0",
            "carbohydrates_g": "6.0",
            "sodium_mg": "150.0",
            "glycemic_index": "45.0",
        }
        # Factor: 100 / 150 = 2/3 ≈ 0.6667
        # 300 * (100/150) = 200.0
        # 30 * (100/150) = 20.0
        # 15 * (100/150) = 10.0
        # 6 * (100/150) = 4.0
        normalized = normalize_nutrients_to_100g(raw, portion_weight_g=150.0)

        assert normalized["energy_kcal"] == Decimal("200.00")
        assert normalized["proteins_g"] == Decimal("20.00")
        assert normalized["lipids_g"] == Decimal("10.00")
        assert normalized["carbohydrates_g"] == Decimal("4.00")
        assert normalized["sodium_mg"] == Decimal("100.00")
        assert normalized["glycemic_index"] == Decimal("45.00")  # IG no se escala

    def test_normalize_nutrients_invalid_weight(self):
        with pytest.raises(ValueError):
            normalize_nutrients_to_100g({"energy_kcal": 100}, portion_weight_g=0)
        with pytest.raises(ValueError):
            normalize_nutrients_to_100g({"energy_kcal": 100}, portion_weight_g=-50)

    def test_scale_nutrients_for_weight(self):
        base_100g = {
            "energy_kcal": 200.0,
            "proteins_g": 20.0,
            "lipids_g": 10.0,
            "carbohydrates_g": 30.0,
        }
        # Escalar a 250g -> Factor 2.5
        scaled = scale_nutrients_for_weight(base_100g, target_weight_g=250.0)
        assert scaled["energy_kcal"] == 500.0
        assert scaled["proteins_g"] == 50.0
        assert scaled["lipids_g"] == 25.0
        assert scaled["carbohydrates_g"] == 75.0

    def test_calculate_glycemic_load_for_portion(self):
        # 30g carbs con IG 50 -> (50 * 30)/100 = 15.0
        res = calculate_glycemic_load_for_portion(carbs_g=30.0, glycemic_index=50.0)
        assert res["cg"] == 15.0
        assert not res["has_missing_ig"]

        # Con carbohidratos pero sin IG
        res_no_ig = calculate_glycemic_load_for_portion(carbs_g=30.0, glycemic_index=None)
        assert res_no_ig["cg"] == 0.0
        assert res_no_ig["has_missing_ig"] is True

        # Sin carbohidratos
        res_no_carbs = calculate_glycemic_load_for_portion(carbs_g=0, glycemic_index=None)
        assert res_no_carbs["cg"] == 0.0
        assert res_no_carbs["has_missing_ig"] is False


# ==============================================================================
# 2. PRUEBAS DE CREACIÓN DE ALIMENTOS AL VUELO (QuickFoodCreateAPIView)
# ==============================================================================

@pytest.mark.django_db
class TestQuickFoodCreateAPIView:
    def test_create_food_with_custom_portion_weight(self, client, user_a):
        client.force_login(user_a)
        category = FoodCategory.objects.create(name="Pescados")
        url = reverse("api_food_create")

        payload = {
            "name": "Salmón Fresco al Horno",
            "category": category.id,
            "portion_type": "custom_weight",
            "portion_weight_g": 200.0,  # Filete de 200g
            "energy_kcal": 400.0,       # 400 kcal para 200g -> 200 kcal / 100g
            "proteins_g": 40.0,         # 40g prot para 200g -> 20g / 100g
            "lipids_g": 24.0,           # 24g grasa para 200g -> 12g / 100g
            "carbohydrates_g": 0.0,
            "sodium_mg": 120.0,         # 120mg para 200g -> 60mg / 100g
            "glycemic_index": 0,
        }

        response = client.post(url, data=json.dumps(payload), content_type="application/json")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["food"]["name"] == "Salmón Fresco al Horno"

        # Verificar en base de datos
        food = Food.objects.get(pk=data["food"]["id"])
        assert food.user == user_a
        assert food.category == category
        assert food.energy_kcal == Decimal("200.00")
        assert food.proteins_g == Decimal("20.00")
        assert food.lipids_g == Decimal("12.00")
        assert food.sodium_mg == Decimal("60.00")

    def test_create_food_standard_100g(self, client, user_a):
        client.force_login(user_a)
        url = reverse("api_food_create")

        payload = {
            "name": "Queso Fresco",
            "portion_type": "100g",
            "energy_kcal": 100.0,
            "proteins_g": 12.0,
            "lipids_g": 4.0,
            "carbohydrates_g": 3.0,
        }

        response = client.post(url, data=json.dumps(payload), content_type="application/json")
        assert response.status_code == 200
        food = Food.objects.get(name="Queso Fresco")
        assert food.user == user_a
        assert food.energy_kcal == Decimal("100.00")
        assert food.proteins_g == Decimal("12.00")

    def test_create_food_validation_empty_name(self, client, user_a):
        client.force_login(user_a)
        url = reverse("api_food_create")
        payload = {"name": "", "energy_kcal": 100}
        response = client.post(url, data=json.dumps(payload), content_type="application/json")
        assert response.status_code == 400
        assert response.json()["success"] is False


# ==============================================================================
# 3. PRUEBAS DE CREACIÓN DE RECETAS AL VUELO (QuickRecipeCreateAPIView)
# ==============================================================================

@pytest.mark.django_db
class TestQuickRecipeCreateAPIView:
    def test_create_recipe_on_the_fly(self, client, user_a):
        client.force_login(user_a)
        food1 = Food.objects.create(name="Arroz Integral", energy_kcal=Decimal("350.0"), proteins_g=Decimal("8.0"), carbohydrates_g=Decimal("75.0"), glycemic_index=Decimal("50.0"))
        food2 = Food.objects.create(name="Pechuga de Pollo", energy_kcal=Decimal("120.0"), proteins_g=Decimal("23.0"), lipids_g=Decimal("2.0"))

        url = reverse("api_recipe_create")
        payload = {
            "name": "Arroz con Pollo Express",
            "servings": 2,
            "description": "Comida rápida post-entreno",
            "instructions": "Hervir arroz y saltear pechuga",
            "ingredients": [
                {"food_id": food1.id, "quantity_g": 150.0},
                {"food_id": food2.id, "quantity_g": 200.0},
            ]
        }

        response = client.post(url, data=json.dumps(payload), content_type="application/json")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        recipe_id = data["recipe"]["id"]

        recipe = Recipe.objects.get(pk=recipe_id)
        assert recipe.user == user_a
        assert recipe.servings == 2
        assert recipe.calculate_total_weight() == 350.0  # 150 + 200
        assert recipe.ingredients.count() == 2

        # Nutrición:
        # Arroz (150g): 350 * 1.5 = 525 kcal, 8 * 1.5 = 12g prot
        # Pollo (200g): 120 * 2 = 240 kcal, 23 * 2 = 46g prot
        # Total: 765 kcal, 58g prot
        nutrition = recipe.calculate_nutrition()
        assert nutrition["energy_kcal"] == 765.0
        assert nutrition["proteins_g"] == 58.0

    def test_create_recipe_empty_ingredients(self, client, user_a):
        client.force_login(user_a)
        url = reverse("api_recipe_create")
        payload = {"name": "Receta Vacía", "ingredients": []}
        response = client.post(url, data=json.dumps(payload), content_type="application/json")
        assert response.status_code == 400
        assert response.json()["success"] is False


# ==============================================================================
# 4. PRUEBAS DE DETALLE Y BÚSQUEDA DE RECETAS/ALIMENTOS
# ==============================================================================

@pytest.mark.django_db
class TestRecipeAndFoodDetailAPIViews:
    def test_recipe_detail_api(self, client, user_a, user_b):
        food = Food.objects.create(name="Pasta", energy_kcal=Decimal("300.0"))
        recipe_a = Recipe.objects.create(user=user_a, name="Pasta User A", servings=1)
        RecipeIngredient.objects.create(recipe=recipe_a, food=food, quantity_g=Decimal("100.0"))

        client.force_login(user_a)
        url = reverse("api_recipe_detail", kwargs={"pk": recipe_a.pk})
        response = client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["recipe"]["ingredients"]) == 1
        assert data["recipe"]["ingredients"][0]["food_name"] == "Pasta"

        # User B no debe poder acceder a la receta de User A
        client.force_login(user_b)
        response_b = client.get(url)
        assert response_b.status_code == 404

    def test_food_search_api_scoping(self, client, user_a, user_b):
        food_global = Food.objects.create(name="Manzana Global", energy_kcal=Decimal("52.0"))
        food_user_a = Food.objects.create(user=user_a, name="Batido Proteína User A", energy_kcal=Decimal("120.0"))
        food_user_b = Food.objects.create(user=user_b, name="Tarta Secreta User B", energy_kcal=Decimal("450.0"))

        client.force_login(user_a)
        url = reverse("api_food_search")
        response = client.get(url)
        assert response.status_code == 200
        foods = response.json()["foods"]
        food_names = [f["name"] for f in foods]

        assert "Manzana Global" in food_names
        assert "Batido Proteína User A" in food_names
        assert "Tarta Secreta User B" not in food_names


# ==============================================================================
# 5. PRUEBAS DE INTEGRACIÓN FOODLOG CON RECETA Y ALIMENTO PROPORCIONAL
# ==============================================================================

@pytest.mark.django_db
class TestFoodLogIntegrationWithProportions:
    def test_food_log_with_recipe_by_weight_and_custom_food(self, test_user=None):
        user = User.objects.create_user(email="cooker@example.com", password="password")
        
        # 1. Crear alimento al vuelo con porción
        raw_nutrients = {"energy_kcal": "200.0", "proteins_g": "20.0", "carbohydrates_g": "10.0"}
        norm = normalize_nutrients_to_100g(raw_nutrients, portion_weight_g=200.0) # 100 kcal / 100g, 10g prot / 100g
        custom_food = Food.objects.create(user=user, name="Ingrediente Especial", **norm)

        # 2. Crear receta al vuelo
        recipe = Recipe.objects.create(user=user, name="Guiso Familiar", servings=4)
        RecipeIngredient.objects.create(recipe=recipe, food=custom_food, quantity_g=Decimal("500.0"))
        # Peso total receta = 500g.
        # Calorías totales receta = 500g * (100kcal/100g) = 500 kcal. Proteínas = 50g.

        # 3. Registrar comida: el usuario comió 250g del guiso (la mitad)
        log = FoodLog.objects.create(user=user, date=timezone.localdate(), meal_type="Almuerzo")
        item = FoodLogItem.objects.create(
            food_log=log,
            recipe=recipe,
            quantity_g=Decimal("250.0")  # 250g de 500g -> factor 0.5
        )

        macros = item.get_nutritional_totals()
        assert macros["calories"] == 250.0  # 500 * 0.5
        assert macros["proteins"] == 25.0   # 50 * 0.5
        assert log.get_total_calories() == 250.0


# ==============================================================================
# 6. PRUEBAS DE PERMISOS Y MUTACIONES DE ALIMENTOS
# ==============================================================================

@pytest.mark.django_db
class TestFoodCustomMutationsAndPermissions:
    def test_user_can_edit_own_food(self, client, user_a):
        category = FoodCategory.objects.create(name="Carnes")
        food = Food.objects.create(user=user_a, name="Mi Alimento", category=category)

        client.force_login(user_a)
        url_edit = reverse("food_edit", kwargs={"pk": food.pk})
        response = client.post(url_edit, {
            "name": "Mi Alimento Modificado",
            "category": category.pk,
            "seasonality": "all"
        })
        assert response.status_code == 302
        food.refresh_from_db()
        assert food.name == "Mi Alimento Modificado"

    def test_user_cannot_edit_other_user_food(self, client, user_a, user_b):
        category = FoodCategory.objects.create(name="Carnes")
        food = Food.objects.create(user=user_b, name="Alimento B", category=category)

        client.force_login(user_a)
        url_edit = reverse("food_edit", kwargs={"pk": food.pk})
        response = client.post(url_edit, {
            "name": "Hackeado",
            "category": category.pk,
            "seasonality": "all"
        })
        assert response.status_code == 403

    def test_user_can_delete_own_food(self, client, user_a):
        category = FoodCategory.objects.create(name="Carnes")
        food = Food.objects.create(user=user_a, name="Mi Alimento Borrable", category=category)

        client.force_login(user_a)
        url_delete = reverse("food_delete", kwargs={"pk": food.pk})
        response = client.post(url_delete)
        assert response.status_code == 302
        assert not Food.objects.filter(pk=food.pk).exists()

