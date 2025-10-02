from django.shortcuts import render
from django.core.cache import cache
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response  # type: ignore
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
try:
    from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
except Exception:
    # Fallback no-op implementations so absence of drf_spectacular doesn't break imports
    def extend_schema(*args, **kwargs):
        def _decorator(func):
            return func
        return _decorator

    class OpenApiParameter:
        def __init__(self, *args, **kwargs):
            pass

    class OpenApiResponse:
        def __init__(self, *args, **kwargs):
            pass
from users.models import User, Passenger, Rider
from users.serializers import UserSerializer, PassengerSerializer, RiderSerializer, UserRegistrationSerializer


class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):

        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()


        refresh = RefreshToken.for_user(user)
        data = {
              'user': UserSerializer(user). data,
              'tokens': {
                  'refresh': str(refresh),
                  'access': str(refresh.access_token),
              },
              'message': 'User registered successfully'
        }
        return Response (data, status=status.HTTP_201_CREATED)


class PassengerViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Passenger instances.
    Provides CRUD operations for passenger profiles.
    """
    queryset = Passenger.objects.all()
    serializer_class = PassengerSerializer
    # permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """
        Filter passengers based on user permissions.
        Regular users can only see their own passenger profile.
        """
        if self.request.user.is_staff:
            return Passenger.objects.all()
        return Passenger.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """
        Associate the passenger with the current user.
        """
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def my_profile(self, request):
        """
        Get the current user's passenger profile.
        """
        try:
            passenger = Passenger.objects.get(user=request.user)
            serializer = self.get_serializer(passenger)
            return Response(serializer.data)
        except Passenger.DoesNotExist:
            return Response(
                {'error': 'Passenger profile not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )


class RiderViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Rider instances.
    Provides CRUD operations for rider profiles.
    """
    queryset = Rider.objects.all()
    serializer_class = RiderSerializer
    # permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """
        Filter riders based on user permissions.
        Regular users can only see their own rider profile.
        Staff can see all riders.
        """
        if self.request.user.is_staff:
            return Rider.objects.all()
        return Rider.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """
        Associate the rider with the current user.
        """
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def my_profile(self, request):
        """
        Get the current user's rider profile.
        """
        try:
            rider = Rider.objects.get(user=request.user)
            serializer = self.get_serializer(rider)
            return Response(serializer.data)
        except Rider.DoesNotExist:
            return Response(
                {'error': 'Rider profile not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'])
    def available_riders(self, request):
        """
        Get all available riders for passengers to see.
        Uses Redis caching with 5-minute timeout.
        """
        cache_key = 'available_riders'
        cached_data = cache.get(cache_key)
        
        if cached_data is not None:
            return Response(cached_data)
        
        available_riders = Rider.objects.filter(
            is_available=True, 
            verification_status='approved'
        )
        serializer = self.get_serializer(available_riders, many=True)
        
        # Cache for 5 minutes (300 seconds)
        cache.set(cache_key, serializer.data, 300)
        return Response(serializer.data)
    
    @action(detail=True, methods=['patch'])
    def update_location(self, request, pk=None):
        """
        Update rider's current location.
        """
        rider = self.get_object()
        if rider.user != request.user and not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        latitude = request.data.get('current_latitude')
        longitude = request.data.get('current_longitude')
        
        if latitude is not None:
            rider.current_latitude = latitude
        if longitude is not None:
            rider.current_longitude = longitude
            
        rider.save()
        
        # Clear available riders cache when location is updated
        cache.delete('available_riders')
        
        serializer = self.get_serializer(rider)
        return Response(serializer.data)


