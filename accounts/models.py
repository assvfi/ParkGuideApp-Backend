# accounts/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    USER_TYPE_LEARNER = 'learner'
    USER_TYPE_ADMIN = 'admin'
    USER_TYPE_CHOICES = (
        (USER_TYPE_LEARNER, 'Learner'),
        (USER_TYPE_ADMIN, 'Admin'),
    )

    email = models.EmailField(unique=True)  # ensure email is unique
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default=USER_TYPE_LEARNER)

    # Fix reverse accessor conflicts
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

    USERNAME_FIELD = 'email'  # <- use email for login
    REQUIRED_FIELDS = ['username']  # still required when creating superusers

    def save(self, *args, **kwargs):
        if self.is_staff or self.is_superuser:
            self.user_type = self.USER_TYPE_ADMIN
            self.is_staff = True
        elif not self.user_type:
            self.user_type = self.USER_TYPE_LEARNER
        super().save(*args, **kwargs)