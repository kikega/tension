import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core import mail
from decimal import Decimal
from accounts.models import AccessRequest
from nutrition.models import Food, FoodCategory
from tracking.models import MeasurementSession

User = get_user_model()

@pytest.fixture
def normal_user(db):
    return User.objects.create_user(email="user@example.com", password="password123", first_name="Juan")

@pytest.fixture
def another_user(db):
    return User.objects.create_user(email="another@example.com", password="password123", first_name="Maria")

@pytest.fixture
def staff_user(db):
    return User.objects.create_user(email="admin@example.com", password="password123", is_staff=True, first_name="Boss")

@pytest.mark.django_db
class TestRegistrationWorkflow:
    def test_signup_creates_inactive_user_and_request(self, client):
        mail.outbox.clear()
        url = reverse("signup")
        data = {
            "email": "newuser@example.com",
            "first_name": "Nuevo",
            "last_name": "Usuario",
            "gender": "male",
            "birth_date": "1995-01-01",
            "height_cm": 175,
            "target_weekly_loss_kg": "0.50",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
        }
        response = client.post(url, data)
        # Should redirect to signup pending page
        assert response.status_code == 302
        assert response.url == reverse("signup_pending")

        # Verify user is created but inactive
        user = User.objects.get(email="newuser@example.com")
        assert not user.is_active

        # Verify AccessRequest is created with pending status
        req = AccessRequest.objects.get(user=user)
        assert req.status == 'pending'

        # Verify email was sent to admin
        assert len(mail.outbox) == 1
        assert "Nueva solicitud de acceso" in mail.outbox[0].subject

    def test_inactive_user_cannot_login(self, client, db):
        # Create an inactive user manually
        user = User.objects.create_user(email="inactive@example.com", password="password123")
        user.is_active = False
        user.save()

        url = reverse("login")
        response = client.post(url, {
            "username": "inactive@example.com",
            "password": "password123"
        })
        # Fails login, stays on login page or redirects back to login with error
        assert not client.session.get('_auth_user_id')

@pytest.mark.django_db
class TestAdminAccessRequestViews:
    def test_normal_user_cannot_access_requests_list(self, client, normal_user):
        client.force_login(normal_user)
        url = reverse("access_requests_list")
        response = client.get(url)
        # 403 Forbidden
        assert response.status_code == 403

    def test_staff_user_can_access_requests_list(self, client, staff_user):
        client.force_login(staff_user)
        url = reverse("access_requests_list")
        response = client.get(url)
        assert response.status_code == 200

    def test_approve_request(self, client, staff_user, normal_user):
        mail.outbox.clear()
        req = AccessRequest.objects.create(user=normal_user, status='pending')
        
        client.force_login(staff_user)
        url = reverse("approve_access_request", kwargs={"pk": req.pk})
        response = client.post(url)
        
        assert response.status_code == 302
        
        # Verify approval
        req.refresh_from_db()
        assert req.status == 'approved'
        normal_user.refresh_from_db()
        assert normal_user.is_active

        # Verify email sent to user
        assert len(mail.outbox) == 1
        assert "aprobada" in mail.outbox[0].subject
        assert normal_user.email in mail.outbox[0].to

    def test_reject_request(self, client, staff_user, normal_user):
        mail.outbox.clear()
        req = AccessRequest.objects.create(user=normal_user, status='pending')
        
        client.force_login(staff_user)
        url = reverse("reject_access_request", kwargs={"pk": req.pk})
        response = client.post(url)
        
        assert response.status_code == 302
        
        # Verify rejection
        req.refresh_from_db()
        assert req.status == 'rejected'
        normal_user.refresh_from_db()
        assert not normal_user.is_active

        # Verify email sent to user
        assert len(mail.outbox) == 1
        assert "solicitud de acceso" in mail.outbox[0].subject
        assert normal_user.email in mail.outbox[0].to

@pytest.mark.django_db
class TestIDORPrevention:
    def test_user_cannot_edit_others_measurement_session(self, client, normal_user, another_user):
        # Create session for another_user
        session = MeasurementSession.objects.create(
            user=another_user,
            time_of_day="morning",
            session_type="control"
        )
        
        client.force_login(normal_user)
        url = reverse("edit_measurement", kwargs={"pk": session.pk})
        response = client.get(url)
        # Should return 404 since get_queryset filters by user
        assert response.status_code == 404

        # POST should also fail with 404
        response_post = client.post(url, {
            "time_of_day": "night",
            "session_type": "intense"
        })
        assert response_post.status_code == 404

@pytest.mark.django_db
class TestFoodPermissionHardening:
    def test_normal_user_cannot_mutate_food(self, client, normal_user):
        category = FoodCategory.objects.create(name="Carnes")
        food = Food.objects.create(name="Pollo", category=category)

        client.force_login(normal_user)

        # 1. Create
        url_add = reverse("food_add")
        response_add = client.post(url_add, {"name": "Pescado", "category": category.pk})
        assert response_add.status_code == 403

        # 2. Update
        url_edit = reverse("food_edit", kwargs={"pk": food.pk})
        response_edit = client.post(url_edit, {"name": "Pollo Editado", "category": category.pk})
        assert response_edit.status_code == 403

        # 3. Delete
        url_delete = reverse("food_delete", kwargs={"pk": food.pk})
        response_delete = client.post(url_delete)
        assert response_delete.status_code == 403

    def test_staff_user_can_mutate_food(self, client, staff_user):
        category = FoodCategory.objects.create(name="Carnes")
        food = Food.objects.create(name="Pollo", category=category)

        client.force_login(staff_user)

        # 1. Create
        url_add = reverse("food_add")
        response_add = client.post(url_add, {
            "name": "Pescado",
            "category": category.pk,
            "seasonality": "all"
        })
        assert response_add.status_code == 302 # Redirect on success
        assert Food.objects.filter(name="Pescado").exists()

        # 2. Update
        url_edit = reverse("food_edit", kwargs={"pk": food.pk})
        response_edit = client.post(url_edit, {
            "name": "Pollo Editado",
            "category": category.pk,
            "seasonality": "all"
        })
        assert response_edit.status_code == 302 # Redirect on success
        food.refresh_from_db()
        assert food.name == "Pollo Editado"

        # 3. Delete
        url_delete = reverse("food_delete", kwargs={"pk": food.pk})
        response_delete = client.post(url_delete)
        assert response_delete.status_code == 302 # Redirect on success
        assert not Food.objects.filter(pk=food.pk).exists()
