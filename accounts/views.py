# accounts/views.py
from rest_framework import generics, permissions, serializers, throttling, status
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.response import Response
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
        self.user = user  # Store user object for response
        return super().validate(attrs)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [throttling.ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as e:
            return Response(e.detail, status=status.HTTP_401_UNAUTHORIZED)
        
        # Get tokens from parent class
        user_obj = getattr(serializer, 'user', None)
        
        # Build response with tokens and user info
        response_data = {
            'access': serializer.validated_data.get('access'),
            'refresh': serializer.validated_data.get('refresh'),
        }
        
        # Add user info if available
        if user_obj:
            role = 'admin' if (user_obj.is_staff or user_obj.is_superuser or user_obj.user_type == 'admin') else 'learner'
            response_data.update({
                'user': {
                    'id': user_obj.id,
                    'username': user_obj.username,
                    'email': user_obj.email,
                    'first_name': user_obj.first_name,
                    'last_name': user_obj.last_name,
                    'is_staff': user_obj.is_staff,
                    'is_superuser': user_obj.is_superuser,
                    'user_type': user_obj.user_type,
                },
                'role': role,
            })
        
        return Response(response_data, status=status.HTTP_200_OK)