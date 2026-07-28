from django.contrib import admin
from jalali_date.admin import ModelAdminJalaliMixin
from .models import Battery, Brand, PurchaseInvoice, PurchaseItem, Sale, SystemSetting


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
  list_display = ("daghi_price_per_amper", "default_profit_percent")


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
  list_display = ("name", "selling_price_per_amper")
  list_editable = (
      "selling_price_per_amper",
  )  # تغییر سریع قیمت روز آمپر از داخل لیست


class PurchaseItemInline(admin.TabularInline):
  model = PurchaseItem
  extra = 1


@admin.register(PurchaseInvoice)
class PurchaseInvoiceAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
  list_display = ("invoice_number", "date_purchased")
  inlines = [PurchaseItemInline]


@admin.register(Battery)
class BatteryAdmin(admin.ModelAdmin):
  list_display = (
      "serial_code",
      "brand",
      "amperage",
      "purchase_price",
      "status",
  )
  list_filter = ("status", "brand", "amperage")
  search_fields = ("serial_code",)


@admin.register(Sale)
class SaleAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
  list_display = (
      "battery",
      "customer_name",
      "final_sale_price",
      "has_daghi",
      "installer",
      "sale_date",
  )
  readonly_fields = (
      "sale_price_without_daghi",
      "daghi_discount",
      "final_sale_price",
  )
  search_fields = (
      "battery__serial_code",
      "customer_name",
      "car_plate",
      "warranty_serial",
  )

  def formfield_for_foreignkey(self, db_field, request, **kwargs):
    if db_field.name == "battery":
      kwargs["queryset"] = Battery.objects.filter(status="available")
    return super().formfield_for_foreignkey(db_field, request, **kwargs)