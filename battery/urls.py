from django.urls import path
from .views import *

urlpatterns = [
    path('dashboard/', dashboard_view, name='battery_dashboard'),
    path('analytics/', analytics_view, name='battery_analytics'),
]