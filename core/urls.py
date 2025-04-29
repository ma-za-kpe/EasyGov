from django.urls import path
from . import views
from .api_views import SummaryViewSet

urlpatterns = [
    path('health/', views.health_check, name='health_check'), 
    path('summaries/', SummaryViewSet.as_view({'get': 'list'}), name='summaries'),
]