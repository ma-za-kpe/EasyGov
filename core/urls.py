from django.urls import path, re_path
from . import views
from .api_views import SummaryViewSet, RegionViewSet

urlpatterns = [
    path('health/', views.health_check, name='health_check'),
    
    # URL patterns with trailing slashes (Django standard)
    path('summaries/', SummaryViewSet.as_view({'get': 'list'}), name='summaries'),
    path('regions/', RegionViewSet.as_view({'get': 'list'}), name='regions'),
    
    # Add the same URL patterns without trailing slashes to prevent redirects
    re_path(r'^summaries$', SummaryViewSet.as_view({'get': 'list'})),
    re_path(r'^regions$', RegionViewSet.as_view({'get': 'list'})),
]