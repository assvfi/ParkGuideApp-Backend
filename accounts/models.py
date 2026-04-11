from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models

malaysia_phone_validator = RegexValidator(
    regex=r"^\+60\d{7,12}$",
    message="Phone number must start with +60 and contain digits only.",
)

class CustomUser(AbstractUser):
    USER_TYPE_LEARNER = 'learner'
    USER_TYPE_ADMIN = 'admin'
    USER_TYPE_CHOICES = (
        (USER_TYPE_LEARNER, 'Learner'),
        (USER_TYPE_ADMIN, 'Admin'),
    )
    email = models.EmailField(unique=True)
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default=USER_TYPE_LEARNER)
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        default='',
        validators=[malaysia_phone_validator],
    )
    birthdate = models.DateField(null=True, blank=True)
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='customuser_set',
        blank=True,
        help_text='The groups this user belongs to.'
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='customuser_permissions_set',
        blank=True,
        help_text='Specific permissions for this user.'
    )
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    def save(self, *args, **kwargs):
        # Normalize Malaysia numbers into +60 format
        if self.phone_number:
            phone = self.phone_number.strip().replace(" ", "").replace("-", "")
            if phone.startswith("0"):
                phone = f"+60{phone[1:]}"
            elif not phone.startswith("+60"):
                phone = f"+60{phone}"
            self.phone_number = phone
        if self.is_staff or self.is_superuser:
            self.user_type = self.USER_TYPE_ADMIN
            self.is_staff = True
        elif not self.user_type:
            self.user_type = self.USER_TYPE_LEARNER
        super().save(*args, **kwargs)