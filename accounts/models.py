from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _

class CustomUserManager(BaseUserManager):
    """Define a model manager for User model with no username field."""

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a User with the given email and password."""
        if not email:
            raise ValueError(_('The Email must be set'))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a SuperUser with the given email and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        return self.create_user(email, password, **extra_fields)

class CustomUser(AbstractUser):
    username = None
    email = models.EmailField(_('email address'), unique=True)
    
    GENDER_CHOICES = [
        ("male", _("Hombre")),
        ("female", _("Mujer")),
    ]
    gender = models.CharField(_("Género"), max_length=6, choices=GENDER_CHOICES, blank=True)
    birth_date = models.DateField(_("Fecha de nacimiento"), null=True, blank=True)
    height_cm = models.PositiveIntegerField(_("Altura (cm)"), null=True, blank=True)
    target_weekly_loss_kg = models.DecimalField(
        _("Objetivo de pérdida semanal (kg)"),
        max_digits=3,
        decimal_places=2,
        default=0.50
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return self.email

    def calculate_bmr(self, current_weight=70.0) -> int:
        """Calcula la Tasa Metabólica Basal (BMR) usando la fórmula de Mifflin-St Jeor."""
        if not self.height_cm or not self.birth_date or not self.gender:
            return 1800 if self.gender == "male" else 1400  # defaults
        
        # Calcular edad
        from datetime import date
        today = date.today()
        age = today.year - self.birth_date.year - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))
        
        weight = float(current_weight)
        height = float(self.height_cm)
        
        if self.gender == "male":
            bmr = 10 * weight + 6.25 * height - 5 * age + 5
        else:
            bmr = 10 * weight + 6.25 * height - 5 * age - 161
            
        return int(bmr)


class AccessRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado'),
    ]
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='access_request')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Solicitud de Acceso"
        verbose_name_plural = "Solicitudes de Acceso"

    def approve(self):
        self.status = 'approved'
        self.user.is_active = True
        self.user.save()
        self.save()

    def reject(self):
        self.status = 'rejected'
        self.user.is_active = False
        self.user.save()
        self.save()

    def __str__(self):
        return f"Solicitud de {self.user.email} - {self.get_status_display()}"

