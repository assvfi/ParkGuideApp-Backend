# accounts/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)  # ensure email is unique

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