from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum
from django.shortcuts import render
from .models import Battery, Brand, PurchaseItem, Sale


@staff_member_required
def dashboard_view(request):
  # ۱. گزارش موجودی انبار به تفکیک برند و آمپر
  available_batteries = Battery.objects.filter(status='available')
  total_available_count = available_batteries.count()

  inventory_summary = (
      available_batteries.values('brand__name', 'amperage')
      .annotate(count=Count('id'))
      .order_by('brand__name', 'amperage')
  )

  # ۲. گزارش داغی‌ها
  sales_with_daghi = Sale.objects.filter(has_daghi=True)
  total_daghi_count = sales_with_daghi.count()

  total_daghi_amperage = sum(
      sale.battery.numeric_amperage for sale in sales_with_daghi
  )

  # ۳. آمار کلی فروش
  total_sales_count = Sale.objects.count()
  total_sales_amount = (
      Sale.objects.aggregate(Sum('final_sale_price'))['final_sale_price__sum']
      or 0
  )

  # ۴. محاسبه جدید: جمع کل فاکتورهای خرید
  # قیمت خرید کل هر آیتم = (آمپر عددی * قیمت خرید هر آمپر) * تعداد
  total_purchase_amount = 0
  for item in PurchaseItem.objects.all():
    total_purchase_amount += (
        item.numeric_amperage * item.purchase_price_per_amper * item.quantity
    )

  context = {
      'total_available_count': total_available_count,
      'inventory_summary': inventory_summary,
      'total_daghi_count': total_daghi_count,
      'total_daghi_amperage': total_daghi_amperage,
      'total_sales_count': total_sales_count,
      'total_sales_amount': total_sales_amount,
      'total_purchase_amount': total_purchase_amount,  # اضافه شد
  }

  return render(request, 'dashboard.html', context)