from django import forms
from django.contrib import admin
from django.db import models
from jalali_date.admin import ModelAdminJalaliMixin
from .models import *


# ۱. مدیریت تنظیمات سیستم (یکپارچه‌شده)
@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
  list_display = (
      'installation_fee',
      'daghi_price_per_amper',
      'default_profit_percent',
  )


# ۲. مدیریت برندها
@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
  list_display = ('name', 'selling_price_per_amper')
  list_editable = ('selling_price_per_amper',)


# ۳. مدیریت فاکتورهای خرید
class PurchaseItemInline(admin.TabularInline):
  model = PurchaseItem
  extra = 1


@admin.register(PurchaseInvoice)
class PurchaseInvoiceAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
  list_display = ('invoice_number', 'date_purchased')
  inlines = [PurchaseItemInline]


# ۴. مدیریت باتری‌های انبار
@admin.register(Battery)
class BatteryAdmin(admin.ModelAdmin):
  list_display = (
      'serial_code',
      'brand',
      'amperage',
      'purchase_price',
      'status',
  )
  list_filter = ('status', 'brand', 'amperage')
  search_fields = ('serial_code',)


# ۵. فرم سفارشی برای رفع باگ نمایش پلاک در SaleAdmin
class SaleAdminForm(forms.ModelForm):

  class Meta:
    model = Sale
    fields = '__all__'
    widgets = {
        'car_plate': forms.TextInput(
            attrs={
                'style': (
                    'direction: ltr; text-align: right; font-family:'
                    ' monospace;'
                ),
                'placeholder': 'مثال: 68-828ق28',
            }
        ),
    }


# ۶. مدیریت فروش‌ها
@admin.register(Sale)
class SaleAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
  form = SaleAdminForm

  list_display = (
      'battery',
      'customer_name',
      'final_sale_price',
      'has_daghi',
      'installer',
      'sale_date',
  )
  readonly_fields = (
      'sale_price_without_daghi',
      'daghi_discount',
      'final_sale_price',
  )
  search_fields = (
      'battery__serial_code',
      'customer_name',
      'car_plate',
      'warranty_serial',
  )

  def formfield_for_foreignkey(self, db_field, request, **kwargs):
    if db_field.name == 'battery':
      object_id = request.resolver_match.kwargs.get('object_id')

      if object_id:
        sale_instance = self.get_object(request, object_id)
        if sale_instance and sale_instance.battery:
          kwargs['queryset'] = Battery.objects.filter(
              models.Q(status='available')
              | models.Q(pk=sale_instance.battery.pk)
          )
      else:
        kwargs['queryset'] = Battery.objects.filter(status='available')

    return super().formfield_for_foreignkey(db_field, request, **kwargs)


# ۷. امکان مدیریت تسویه‌ها و تراکنش‌های کیف پول نصاب‌ها
@admin.register(InstallerTransaction)
class InstallerTransactionAdmin(admin.ModelAdmin):
  list_display = (
      'installer',
      'transaction_type',
      'formatted_amount',
      'date',
      'description',
  )
  list_filter = ('transaction_type', 'date', 'installer')
  search_fields = (
      'installer__username',
      'installer__first_name',
      'installer__last_name',
      'description',
  )
  date_hierarchy = 'date'

  def formatted_amount(self, obj):
    return f'{obj.amount:,} تومان'

  formatted_amount.short_description = 'مبلغ'