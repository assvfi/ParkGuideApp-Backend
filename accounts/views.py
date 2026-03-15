# accounts/views.py
from rest_framework import generics, permissions, serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .serializers import RegisterSerializer, UserSerializer

User = get_user_model()

# -------------------------
# Registration endpoint
# -------------------------
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

# -------------------------
# Custom JWT login using email
# -------------------------
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'  # tells the serializer we’re using email

    def validate(self, attrs):
        # Make sure email and password exist
        email = attrs.get('email')
        password = attrs.get('password')

        if not email or not password:
            raise serializers.ValidationError({"detail": "Email and password are required."})

        # Find user by email
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({"detail": "No active account found with the given credentials"})

        # Check password
        if not user.check_password(password):
            raise serializers.ValidationError({"detail": "No active account found with the given credentials"})

        # Pass username to parent serializer
        attrs['username'] = user.username
        return super().validate(attrs)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer