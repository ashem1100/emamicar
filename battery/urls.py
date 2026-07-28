from django.urls import path
from .views import *

urlpatterns = [
    path('dashboard/', dashboard_view, name='battery_dashboard'),
    path('analytics/', analytics_view, name='battery_analytics'),
    path('sales/', sale_list_view, name='sale_list'),
    path('sales/<int:pk>/', sale_detail_view, name='sale_detail'),
    path('sales/add/', sale_create_view, name='sale_create'),
]