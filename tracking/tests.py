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
