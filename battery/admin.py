from django.contrib import admin
from .models import Battery, Purchase, Sale


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
  list_display = (
      "invoice_number",
      "brand",
      "amperage",
      "quantity",
      "purchase_price_per_amper",
      "date_purchased",
  )
  search_fields = ("invoice_number", "brand")
  list_filter = ("brand", "amperage", "date_purchased")


@admin.register(Battery)
class BatteryAdmin(admin.ModelAdmin):
  list_display = (
      "serial_code",
      "brand",
      "amperage",
      "status",
      "purchase_invoice",
  )
  list_filter = ("status", "brand", "amperage")
  search_fields = ("serial_code", "brand")
  # امکان ویرایش سریع وضعیت از داخل جدول ادمین
  list_editable = ("status",)

  # نمایش شماره فاکتور خرید در جدول
  def purchase_invoice(self, obj):
    return obj.purchase.invoice_number

  purchase_invoice.short_description = "شماره فاکتور خرید"


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
  list_display = (
      "battery",
      "get_brand",
      "get_amperage",
      "customer_name",
      "customer_phone",
      "warranty_serial",
      "daghi_price",
      "installer_name",
      "sale_date",
  )
  search_fields = (
      "battery__serial_code",
      "customer_name",
      "customer_phone",
      "car_plate",
      "warranty_serial",
  )
  list_filter = ("sale_date", "installer_name")

  # نمایش برند و آمپر در جدول فروش
  def get_brand(self, obj):
    return obj.battery.brand

  get_brand.short_description = "برند"

  def get_amperage(self, obj):
    return obj.battery.amperage

  get_amperage.short_description = "آمپر"

  # فقط نشان دادن باتری‌های «موجود» در لیست کشوییِ فرم فروش
  def formfield_for_foreignkey(self, db_field, request, **kwargs):
    if db_field.name == "battery":
      kwargs["queryset"] = Battery.objects.filter(status="available")
    return super().formfield_for_foreignkey(db_field, request, **kwargs)