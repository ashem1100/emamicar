from datetime import timedelta
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum
from django.shortcuts import render
from django.utils import timezone
from .models import Battery, Brand, PurchaseInvoice, PurchaseItem, Sale
import json
from django.db.models.functions import ExtractMonth
from django.http import JsonResponse


@staff_member_required
def dashboard_view(request):
  # ۱. گرفتن فیلتر زمانی از آدرس (پیش‌فرض: all = کل دوره)
  period = request.GET.get('period', 'all')
  now = timezone.now().date()

  # ساخت کوئری پایه برای فروش‌ها
  sales_queryset = Sale.objects.all()

  # ۲. اعمال فیلتر زمانی روی فروش‌ها
  if period == 'today':
    sales_queryset = sales_queryset.filter(sale_date=now)
  elif period == 'week':
    start_date = now - timedelta(days=7)
    sales_queryset = sales_queryset.filter(
        sale_date__gte=start_date, sale_date__lte=now
    )
  elif period == 'month':
    start_date = now - timedelta(days=30)
    sales_queryset = sales_queryset.filter(
        sale_date__gte=start_date, sale_date__lte=now
    )
  elif period == 'year':
    sales_queryset = sales_queryset.filter(sale_date__year=now.year)

  # ۳. آمار موجودی انبار (موجودی فعلی به بازه زمانی ربطی ندارد و همواره لحظه‌ای است)
  available_batteries = Battery.objects.filter(status='available')
  total_available_count = available_batteries.count()

  inventory_summary = (
      available_batteries.values('brand__name', 'amperage')
      .annotate(count=Count('id'))
      .order_by('brand__name', 'amperage')
  )

  # ۴. محاسبه آمار داغی‌ها بر اساس فیلتر زمانی انتخاب شده
  sales_with_daghi = sales_queryset.filter(has_daghi=True)
  total_daghi_count = sales_with_daghi.count()

  total_daghi_amperage = sum(
      sale.numeric_daghi_amperage for sale in sales_with_daghi
  )

  # ۵. محاسبه مالی فروش بر اساس فیلتر زمانی
  total_sales_count = sales_queryset.count()
  total_sales_amount = (
      sales_queryset.aggregate(Sum('final_sale_price'))[
          'final_sale_price__sum'
      ]
      or 0
  )

  # ۶. مجموع کل فاکتورهای خرید (برای کل دوره)
  total_purchase_amount = 0
  for item in PurchaseItem.objects.all():
    total_purchase_amount += (
        item.numeric_amperage * item.purchase_price_per_amper * item.quantity
    )

  context = {
      'period': period,
      'total_available_count': total_available_count,
      'inventory_summary': inventory_summary,
      'total_daghi_count': total_daghi_count,
      'total_daghi_amperage': total_daghi_amperage,
      'total_sales_count': total_sales_count,
      'total_sales_amount': total_sales_amount,
      'total_purchase_amount': total_purchase_amount,
  }

  return render(request, 'dashboard.html', context)


@staff_member_required
def analytics_view(request):
  # ۱. آمار فروش به تفکیک برند (برای نمودار دایره‌ای)
  brand_sales = (
      Sale.objects.values('battery__brand__name')
      .annotate(total_count=Count('id'), total_amount=Sum('final_sale_price'))
      .order_by('-total_count')
  )

  brand_labels = [item['battery__brand__name'] for item in brand_sales]
  brand_counts = [item['total_count'] for item in brand_sales]

  # ۲. آمار فروش به تفکیک آمپر (برای نمودار دونات)
  amper_sales = (
      Sale.objects.values('battery__amperage')
      .annotate(total_count=Count('id'))
      .order_by('-total_count')
  )

  amper_labels = [f"{item['battery__amperage']} آمپر" for item in amper_sales]
  amper_counts = [item['total_count'] for item in amper_sales]

  # ۳. آمار روند فروش ماهانه (برای نمودار خطی)
  monthly_sales = (
      Sale.objects.annotate(month=ExtractMonth('sale_date'))
      .values('month')
      .annotate(total_amount=Sum('final_sale_price'), count=Count('id'))
      .order_by('month')
  )

  month_names = {
      1: 'فروردین',
      2: 'اردیبهشت',
      3: 'خرداد',
      4: 'تیر',
      5: 'مرداد',
      6: 'شهریور',
      7: 'مهر',
      8: 'آبان',
      9: 'آذر',
      10: 'دی',
      11: 'بهمن',
      12: 'اسفند',
  }
  monthly_labels = [
      month_names.get(item['month'], str(item['month']))
      for item in monthly_sales
  ]
  monthly_amounts = [
      float(item['total_amount'] or 0) for item in monthly_sales
  ]

  context = {
      'brand_labels': json.dumps(brand_labels),
      'brand_counts': json.dumps(brand_counts),
      'amper_labels': json.dumps(amper_labels),
      'amper_counts': json.dumps(amper_counts),
      'monthly_labels': json.dumps(monthly_labels),
      'monthly_amounts': json.dumps(monthly_amounts),
  }

  return render(request, 'analytics.html', context)