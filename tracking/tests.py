import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from tracking.models import WeightMeasurement
from tracking.forms import WeightMeasurementForm

User = get_user_model()

@pytest.fixture
def test_user(db):
    return User.objects.create_user(email="test@example.com", password="password")

@pytest.mark.django_db
class TestWeightMeasurementModel:
    def test_create_weight_measurement(self, test_user):
        """Test creating a simple weight measurement"""
        measurement = WeightMeasurement.objects.create(
            user=test_user,
            weight=Decimal('80.5'),
            date=timezone.localdate()
        )
        assert measurement.user == test_user
        assert measurement.weight == Decimal('80.5')
        assert measurement.lean_mass_kg is None
        assert measurement.fat_mass_kg is None
        assert str(measurement) == f"{measurement.date} - 80.5 kg"

    def test_create_weight_measurement_with_body_composition(self, test_user):
        """Test creating a weight measurement with optional body composition fields"""
        measurement = WeightMeasurement.objects.create(
            user=test_user,
            weight=Decimal('80.5'),
            lean_mass_kg=Decimal('62.5'),
            fat_mass_kg=Decimal('18.0'),
            date=timezone.localdate()
        )
        assert measurement.weight == Decimal('80.5')
        assert measurement.lean_mass_kg == Decimal('62.5')
        assert measurement.fat_mass_kg == Decimal('18.0')

    def test_imc_calculations(self, test_user):
        """Test BMI calculations and classifications"""
        # User has no height defined
        measurement = WeightMeasurement.objects.create(
            user=test_user,
            weight=Decimal('80.0'),
            date=timezone.localdate()
        )
        assert measurement.imc is None
        assert measurement.imc_classification is None

        # Set user height
        test_user.height_cm = 180
        test_user.save()

        # Weight: 80.0. height: 180cm. IMC: 80.0 / 1.8**2 = 24.69 -> Normal
        assert measurement.imc == 24.69
        assert measurement.imc_classification == "Normal"

        # Weight: 55.0 -> Bajo peso
        measurement.weight = Decimal('55.0')
        measurement.save()
        assert measurement.imc == 16.98
        assert measurement.imc_classification == "Bajo peso"

        # Weight: 90.0 -> Sobrepeso
        measurement.weight = Decimal('90.0')
        measurement.save()
        assert measurement.imc == 27.78
        assert measurement.imc_classification == "Sobrepeso"

        # Weight: 100.0 -> Obesidad
        measurement.weight = Decimal('100.0')
        measurement.save()
        assert measurement.imc == 30.86
        assert measurement.imc_classification == "Obesidad"

@pytest.mark.django_db
class TestWeightMeasurementForm:
    def test_valid_form(self, test_user):
        data = {'weight': '80.5', 'date': timezone.localdate()}
        form = WeightMeasurementForm(data=data)
        assert form.is_valid()
    
    def test_invalid_form_negative_weight(self, test_user):
        data = {'weight': '-5.0', 'date': timezone.localdate()}
        form = WeightMeasurementForm(data=data)
        assert not form.is_valid()


@pytest.mark.django_db
class TestWeightViews:
    def test_weight_create_view(self, client, test_user):
        client.force_login(test_user)
        url = reverse('add_weight')
        response = client.post(url, {
            'date': timezone.localdate().strftime('%Y-%m-%d'),
            'weight': '80.5',
            'lean_mass_kg': '62.0',
            'fat_mass_kg': '18.5'
        })
        assert response.status_code == 302 # Redirects on success
        assert WeightMeasurement.objects.filter(
            user=test_user,
            weight=Decimal('80.5'),
            lean_mass_kg=Decimal('62.0'),
            fat_mass_kg=Decimal('18.5')
        ).exists()

    def test_weight_list_view_calculations(self, client, test_user):
        client.force_login(test_user)
        
        # Create older measurement first
        old_date = timezone.now().date() - timezone.timedelta(days=7)
        WeightMeasurement.objects.create(user=test_user, weight=Decimal('80.0'), date=old_date)
        
        # Create recent measurement
        recent_date = timezone.now().date()
        WeightMeasurement.objects.create(user=test_user, weight=Decimal('79.2'), date=recent_date)
        
        url = reverse('weight_history')
        response = client.get(url)
        
        assert response.status_code == 200
        # Check context
        sessions_context = response.context['weight_measurements']
        assert len(sessions_context) == 2
        
        # recent measurement should be first due to ordering '-date'
        recent = sessions_context[0]
        older = sessions_context[1]
        
        assert recent.weight == Decimal('79.2')
        assert recent.peso_perdido == Decimal('0.8')  # 80.0 - 79.2
        assert round(recent.porcentaje, 2) == Decimal('1.00')  # 0.8 / 80.0 * 100
        
        assert older.peso_perdido == Decimal('0.0')

        assert 'total_weight_diff' in response.context
        assert 'total_weight_diff_pct' in response.context
        assert response.context['total_weight_diff'] == Decimal('0.8')
        assert round(response.context['total_weight_diff_pct'], 2) == Decimal('1.00')

    def test_dashboard_weight_context(self, client, test_user):
        client.force_login(test_user)
        WeightMeasurement.objects.create(user=test_user, weight=Decimal('80.0'), date=timezone.localdate())
        
        url = reverse('dashboard')
        response = client.get(url)
        assert response.status_code == 200
        assert 'weight_data' in response.context
        assert 'weight_labels' in response.context


@pytest.mark.django_db
class TestGlycemicCalculations:
    def test_glycemic_load_calculations(self, test_user):
        from nutrition.models import Food, Recipe, RecipeIngredient
        from tracking.models import FoodLog, FoodLogItem
        
        # 1. Create foods with various IGs and carbs
        food_low = Food.objects.create(
            name="Manzana",
            carbohydrates_g=Decimal("12.00"),
            glycemic_index=Decimal("35.00")
        )
        food_high = Food.objects.create(
            name="Pan Blanco",
            carbohydrates_g=Decimal("50.00"),
            glycemic_index=Decimal("75.00")
        )
        food_no_ig = Food.objects.create(
            name="Alimento Misterioso",
            carbohydrates_g=Decimal("20.00"),
            glycemic_index=None
        )
        food_no_carbs = Food.objects.create(
            name="Filete",
            carbohydrates_g=Decimal("0.00"),
            glycemic_index=None
        )

        # 2. Create food log
        log = FoodLog.objects.create(
            user=test_user,
            date=timezone.localdate(),
            meal_type="Almuerzo"
        )

        # 3. Test Low IG portion: 150g manzana
        # Carbs: 12g * 1.5 = 18g
        # CG: (35 * 18) / 100 = 6.3
        item1 = FoodLogItem.objects.create(
            food_log=log,
            food=food_low,
            quantity_g=Decimal("150.00")
        )
        cg_data1 = item1.get_glycemic_load()
        assert cg_data1["cg"] == 6.3
        assert not cg_data1["has_missing_ig"]

        # 4. Test High IG portion: 80g pan blanco
        # Carbs: 50g * 0.8 = 40g
        # CG: (75 * 40) / 100 = 30.0
        item2 = FoodLogItem.objects.create(
            food_log=log,
            food=food_high,
            quantity_g=Decimal("80.00")
        )
        cg_data2 = item2.get_glycemic_load()
        assert cg_data2["cg"] == 30.0
        assert not cg_data2["has_missing_ig"]

        # 5. Test food with carbs but no IG
        item3 = FoodLogItem.objects.create(
            food_log=log,
            food=food_no_ig,
            quantity_g=Decimal("100.00")
        )
        cg_data3 = item3.get_glycemic_load()
        assert cg_data3["cg"] == 0.0
        assert cg_data3["has_missing_ig"]

        # 6. Test food with 0 carbs and no IG
        item4 = FoodLogItem.objects.create(
            food_log=log,
            food=food_no_carbs,
            quantity_g=Decimal("200.00")
        )
        cg_data4 = item4.get_glycemic_load()
        assert cg_data4["cg"] == 0.0
        assert not cg_data4["has_missing_ig"]

        # 7. Test Recipe
        recipe = Recipe.objects.create(name="Ensalada y Pan", servings=2)
        RecipeIngredient.objects.create(recipe=recipe, food=food_low, quantity_g=Decimal("100.00")) # Carbs: 12g, CG: (35 * 12)/100 = 4.2
        RecipeIngredient.objects.create(recipe=recipe, food=food_high, quantity_g=Decimal("40.00")) # Carbs: 20g, CG: (75 * 20)/100 = 15.0
        # Recipe Total CG: 4.2 + 15.0 = 19.2
        # Servings = 2, so CG per serving = 9.6
        
        # Consumed item: 1.5 servings of recipe -> CG: 9.6 * 1.5 = 14.4
        item_recipe = FoodLogItem.objects.create(
            food_log=log,
            recipe=recipe,
            servings=Decimal("1.5")
        )
        cg_data_recipe = item_recipe.get_glycemic_load()
        assert cg_data_recipe["cg"] == 14.4
        assert not cg_data_recipe["has_missing_ig"]

        # 8. Test overall FoodLog CG
        # Total CG: 6.3 + 30.0 + 0.0 + 0.0 + 14.4 = 50.7
        # has_missing_ig: True (because of item3)
        log_cg_data = log.get_glycemic_load()
        assert log_cg_data["cg"] == 50.7
        assert log_cg_data["has_missing_ig"]


@pytest.mark.django_db
class TestAppleWatchAndKarateEstimation:
    def test_bmr_calculation(self, test_user):
        """Test Mifflin-St Jeor BMR calculation."""
        # 1. Without profile data: defaults
        assert test_user.calculate_bmr(80.0) == 1400 # female/no gender default is 1400

        # Set profile
        test_user.gender = "male"
        test_user.height_cm = 180
        from datetime import date
        test_user.birth_date = date(1990, 6, 5) # 36 years old in 2026
        test_user.save()

        # BMR male: 10 * 80 + 6.25 * 180 - 5 * 36 + 5 = 800 + 1125 - 180 + 5 = 1750
        assert test_user.calculate_bmr(80.0) == 1750

    def test_karate_calories_estimation(self, test_user):
        """Test MET active exercise estimation for Karate."""
        from tracking.models import PhysicalActivity, PhysicalActivityLog
        
        # Create weight
        WeightMeasurement.objects.create(
            user=test_user,
            weight=Decimal('80.0'),
            date=timezone.localdate()
        )

        activity_karate = PhysicalActivity.objects.create(
            user=test_user,
            name="Karate",
            met_value=Decimal('8.0'),
            default_not_tracked_by_watch=True
        )

        # Log Karate workout: 60 minutes
        log = PhysicalActivityLog.objects.create(
            user=test_user,
            activity=activity_karate,
            duration_minutes=60,
            date=timezone.localdate()
        )

        # Calories: MET (8) * weight (80) * duration (1.0 hour) = 640 kcal
        assert log.estimated_calories == 640
        assert log.not_tracked_by_watch is True

    def test_daily_activity_summary_and_balance(self, test_user):
        """Test DailyActivityLog energy expenditure and caloric balance."""
        from tracking.models import DailyActivityLog, FoodLog, FoodLogItem, PhysicalActivity, PhysicalActivityLog
        from nutrition.models import Food

        # Create weight
        WeightMeasurement.objects.create(
            user=test_user,
            weight=Decimal('80.0'),
            date=timezone.localdate()
        )

        # Log Karate workout (estimated: 640 kcal)
        activity_karate = PhysicalActivity.objects.create(
            user=test_user,
            name="Karate",
            met_value=Decimal('8.0'),
            default_not_tracked_by_watch=True
        )
        PhysicalActivityLog.objects.create(
            user=test_user,
            activity=activity_karate,
            duration_minutes=60,
            date=timezone.localdate()
        )

        # Daily log: active 300, resting 1800, steps 10000, distance 8.0
        daily_log = DailyActivityLog.objects.create(
            user=test_user,
            date=timezone.localdate(),
            active_calories=300,
            resting_calories=1800,
            steps=10000,
            distance_km=Decimal("8.00")
        )

        # Total burned: resting (1800) + active (300) + extra exercise (Karate: 640) = 2740 kcal
        assert daily_log.extra_exercise_calories == 640
        assert daily_log.get_total_calories_burned() == 2740

        # Food log: 2000 kcal
        food = Food.objects.create(name="Super comida", energy_kcal=Decimal("1000.0"))
        food_log = FoodLog.objects.create(user=test_user, date=timezone.localdate(), meal_type="Cena")
        FoodLogItem.objects.create(food_log=food_log, food=food, quantity_g=Decimal("200.0")) # 2 * 1000 = 2000 kcal

        # Balance: 2000 - 2740 = -740 kcal
        assert daily_log.get_caloric_balance() == -740.0


@pytest.mark.django_db
class TestUserRegistration:
    def test_signup_view_get(self, client):
        url = reverse("signup")
        response = client.get(url)
        assert response.status_code == 200
        assert "Crear Cuenta" in response.content.decode("utf-8")

    def test_signup_view_post_success(self, client):
        url = reverse("signup")
        data = {
            "email": "registered@example.com",
            "first_name": "Juan",
            "last_name": "Pérez",
            "gender": "male",
            "birth_date": "1990-01-01",
            "height_cm": 180,
            "target_weekly_loss_kg": "0.75",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
        }
        response = client.post(url, data)
        # Should redirect to signup pending
        assert response.status_code == 302
        assert response.url == reverse("signup_pending")
        
        # Verify user creation
        new_user = User.objects.get(email="registered@example.com")
        assert not new_user.is_active
        assert new_user.first_name == "Juan"
        assert new_user.last_name == "Pérez"
        assert new_user.gender == "male"
        assert str(new_user.birth_date) == "1990-01-01"
        assert new_user.height_cm == 180
        assert new_user.target_weekly_loss_kg == Decimal("0.75")
        assert new_user.check_password("SecurePass123!")


@pytest.mark.django_db
class TestRecipeMultiUser:
    def test_recipe_scoping(self, client, test_user):
        from nutrition.models import Recipe
        other_user = User.objects.create_user(email="other@example.com", password="password")
        
        # Create global recipe (no user)
        recipe_global = Recipe.objects.create(name="Receta Global", servings=2)
        # Create user's recipe
        recipe_user = Recipe.objects.create(name="Mi Receta", user=test_user, servings=1)
        # Create other user's recipe
        recipe_other = Recipe.objects.create(name="Receta Ajena", user=other_user, servings=3)
        
        client.force_login(test_user)
        
        # 1. Test List View
        url = reverse("recipe_list")
        response = client.get(url)
        assert response.status_code == 200
        recipes_context = list(response.context["recipes"])
        # Should contain global and user's own, but NOT other user's
        assert recipe_global in recipes_context
        assert recipe_user in recipes_context
        assert recipe_other not in recipes_context
        
        # 2. Test Detail View access
        # Can see own recipe
        url_own = reverse("recipe_detail", kwargs={"pk": recipe_user.pk})
        response_own = client.get(url_own)
        assert response_own.status_code == 200
        
        # Can see global recipe
        url_global = reverse("recipe_detail", kwargs={"pk": recipe_global.pk})
        response_global = client.get(url_global)
        assert response_global.status_code == 200
        
        # Cannot see other user's recipe (should return 404)
        url_other = reverse("recipe_detail", kwargs={"pk": recipe_other.pk})
        response_other = client.get(url_other)
        assert response_other.status_code == 404

    def test_recipe_ownership_mutations(self, client, test_user):
        from nutrition.models import Recipe
        other_user = User.objects.create_user(email="other@example.com", password="password")
        
        # Create other user's recipe
        recipe_other = Recipe.objects.create(name="Receta Ajena", user=other_user, servings=3)
        
        client.force_login(test_user)
        
        # Cannot edit other user's recipe (should return 404)
        url_edit = reverse("recipe_edit", kwargs={"pk": recipe_other.pk})
        response_edit = client.post(url_edit, {"name": "Hackeado", "servings": 4})
        assert response_edit.status_code == 404
        
        # Cannot delete other user's recipe (should return 404)
        url_delete = reverse("recipe_delete", kwargs={"pk": recipe_other.pk})
        response_delete = client.post(url_delete)
        assert response_delete.status_code == 404


@pytest.mark.django_db
class TestFoodLogAndEatenOut:
    def test_eaten_out_calorie_adjustment(self, test_user):
        """Test that FoodLog get_total_calories applies correct penalty/adjustment when eaten_out is True"""
        from nutrition.models import Food
        from tracking.models import FoodLog, FoodLogItem

        # Food with 100 kcal per 100g
        food = Food.objects.create(name="Arroz", energy_kcal=Decimal("100.0"))
        
        # 1. eaten_out = False (Normal calories)
        log_normal = FoodLog.objects.create(user=test_user, date=timezone.localdate(), meal_type="Almuerzo", eaten_out=False)
        FoodLogItem.objects.create(food_log=log_normal, food=food, quantity_g=Decimal("200.0")) # 200 kcal
        assert log_normal.get_total_calories() == 200.0

        # 2. eaten_out = True with food items (Calculated: 200 kcal * 1.3 + 500 = 760 kcal)
        log_eaten_out = FoodLog.objects.create(user=test_user, date=timezone.localdate(), meal_type="Almuerzo", eaten_out=True)
        FoodLogItem.objects.create(food_log=log_eaten_out, food=food, quantity_g=Decimal("200.0"))
        assert log_eaten_out.get_total_calories() == 760.0

        # 3. eaten_out = True with no food items (Minimum 800 kcal fallback)
        log_empty_eaten_out = FoodLog.objects.create(user=test_user, date=timezone.localdate(), meal_type="Almuerzo", eaten_out=True)
        assert log_empty_eaten_out.get_total_calories() == 800.0

    def test_recipe_filtering_in_formset(self, client, test_user):
        """Test that the food_log_add view renders the formset filtering recipes to only user-owned and global ones"""
        from nutrition.models import Recipe
        other_user = User.objects.create_user(email="other@example.com", password="password")
        
        # Create recipes
        recipe_global = Recipe.objects.create(name="Receta Global", servings=2)
        recipe_user = Recipe.objects.create(name="Mi Receta", user=test_user, servings=1)
        recipe_other = Recipe.objects.create(name="Receta Ajena", user=other_user, servings=3)

        client.force_login(test_user)
        response = client.get(reverse("food_log_add"))
        assert response.status_code == 200
        
        # Check that recipe queryset in context items formset contains global and user recipes, but not other
        formset = response.context["items"]
        recipe_field = formset.forms[0].fields["recipe"]
        queryset = list(recipe_field.queryset)
        
        assert recipe_global in queryset
        assert recipe_user in queryset
        assert recipe_other not in queryset

    def test_eat_out_ai_insights(self, test_user):
        """Test that generate_insights correctly incorporates eating out analysis and recommendations"""
        from tracking.services.ai_analysis import generate_insights
        from tracking.models import FoodLog, WeightMeasurement
        
        # Create some baseline weight data
        for i in range(10):
            d = timezone.localdate() - timezone.timedelta(days=10-i)
            WeightMeasurement.objects.create(user=test_user, weight=Decimal(str(80.0 - i * 0.1)), date=d)
            
        # Create food log with eating out
        FoodLog.objects.create(user=test_user, date=timezone.localdate() - timezone.timedelta(days=2), meal_type="Cena", eaten_out=True)
        
        insights_data = generate_insights(test_user)
        assert "insights" in insights_data
        
        # Since we have less than 5 weight differences + eating out data points, the fallback warning should trigger
        has_eat_out_insight = any(
            insight["title"] in ["Impacto de Comer Fuera de Casa", "Comidas Fuera de Casa"]
            for insight in insights_data["insights"]
        )
        assert has_eat_out_insight


