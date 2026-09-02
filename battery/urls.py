from django.urls import path
from .views import *
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('dashboard/', dashboard_view, name='battery_dashboard'),
    path('analytics/', analytics_view, name='battery_analytics'),
    path('sales/', sale_list_view, name='sale_list'),
    path('sales/<int:pk>/', sale_detail_view, name='sale_detail'),
    path('sales/quick-add-battery/', quick_add_battery_view, name='quick_add_battery'),

    path('sales/add/', sale_create_view, name='sale_create'),
    path('panel/', installer_dashboard_view, name='installer_dashboard'),
    path('panel/sale/', installer_sale_list_view, name='installer_sale_list'),
    path('panel/sale/add/', installer_sale_create_view, name='installer_sale_create'),
# مسیرهای ورود و خروج
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    # مسیرهای مدیریت کیف پول نصاب‌ها (برای ادمین)
    path('installers/', installer_management_view, name='installer_management'),
    path('installers/payout/<int:user_id>/', installer_payout_view, name='installer_payout'),

    # مسیر کیف پول نصاب (برای پنل خودش)
    path('panel/wallet/', installer_wallet_view, name='installer_wallet'),

]


