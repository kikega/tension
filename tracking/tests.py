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
        assert str(measurement) == f"{measurement.date} - 80.5 kg"

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
            'weight': '80.5'
        })
        assert response.status_code == 302 # Redirects on success
        assert WeightMeasurement.objects.filter(user=test_user, weight=Decimal('80.5')).exists()

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

