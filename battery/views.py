from datetime import timedelta
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.db.models import Count, Sum
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from .models import Battery, Brand, PurchaseInvoice, PurchaseItem, Sale
import json
from django.db.models.functions import ExtractMonth
from django.http import JsonResponse
import jdatetime
from django.contrib import messages
from django.db.models import Q

from collections import defaultdict


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
  start_date_shamsi = request.GET.get('start_date', '')
  end_date_shamsi = request.GET.get('end_date', '')

  sales_queryset = Sale.objects.all()

  # فیلتر تاریخ شمسی
  if start_date_shamsi:
    try:
      parts = [int(x) for x in start_date_shamsi.split('/')]
      start_gregorian = jdatetime.date(
          parts[0], parts[1], parts[2]
      ).togregorian()
      sales_queryset = sales_queryset.filter(sale_date__gte=start_gregorian)
    except ValueError:
      pass

  if end_date_shamsi:
    try:
      parts = [int(x) for x in end_date_shamsi.split('/')]
      end_gregorian = jdatetime.date(parts[0], parts[1], parts[2]).togregorian()
      sales_queryset = sales_queryset.filter(sale_date__lte=end_gregorian)
    except ValueError:
      pass

  # ۱. آمار برندها
  brand_sales = (
      sales_queryset.values('battery__brand__name')
      .annotate(total_count=Count('id'))
      .order_by('-total_count')
  )
  brand_labels = [item['battery__brand__name'] for item in brand_sales]
  brand_counts = [item['total_count'] for item in brand_sales]

  # ۲. آمار آمپرها
  amper_sales = (
      sales_queryset.values('battery__amperage')
      .annotate(total_count=Count('id'))
      .order_by('-total_count')
  )
  amper_labels = [f"{item['battery__amperage']} آمپر" for item in amper_sales]
  amper_counts = [item['total_count'] for item in amper_sales]

  # ۳. آمار روند فروش بر اساس ماه شمسی واقعی
  shamsi_months = [
      'فروردین',
      'اردیبهشت',
      'خرداد',
      'تیر',
      'مرداد',
      'شهریور',
      'مهر',
      'آبان',
      'آذر',
      'دی',
      'بهمن',
      'اسفند',
  ]

  # دیکشنری برای جمع زدن فروش‌های هر ماه شمسی
  monthly_data = defaultdict(float)

  # پیمایش تمام فروش‌ها و تبدیل تک‌تک تاریخ‌ها به ماه شمسی دقیق
  for sale in sales_queryset:
    if sale.sale_date:
      j_date = jdatetime.date.fromgregorian(date=sale.sale_date)
      # کلید به صورت (کد_ماه, نام_ماه) برای مرتب‌سازی درست
      month_key = (j_date.month, shamsi_months[j_date.month - 1])
      monthly_data[month_key] += float(sale.final_sale_price or 0)

  # مرتب‌سازی بر اساس شماره ماه شمسی (از فروردین تا اسفند)
  sorted_months = sorted(monthly_data.items(), key=lambda x: x[0][0])

  monthly_labels = [item[0][1] for item in sorted_months]
  monthly_amounts = [item[1] for item in sorted_months]

  context = {
      'brand_labels': json.dumps(brand_labels),
      'brand_counts': json.dumps(brand_counts),
      'amper_labels': json.dumps(amper_labels),
      'amper_counts': json.dumps(amper_counts),
      'monthly_labels': json.dumps(monthly_labels),
      'monthly_amounts': json.dumps(monthly_amounts),
      'start_date': start_date_shamsi,
      'end_date': end_date_shamsi,
  }

  return render(request, 'analytics.html', context)


@staff_member_required
def sale_list_view(request):
    sales = Sale.objects.select_related('battery', 'battery__brand').all().order_by('-sale_date')

    # ۱. جستجو (نام، پلاک، تلفن، سریال باتری)
    search_query = request.GET.get('search', '')
    if search_query:
        sales = sales.filter(
            Q(customer_name__icontains=search_query) |
            Q(customer_phone__icontains=search_query) |
            Q(car_plate__icontains=search_query) |
            Q(battery__serial_code__icontains=search_query)
        )

    # ۲. فیلتر برند و آمپر
    brand_id = request.GET.get('brand', '')
    amperage = request.GET.get('amperage', '')
    if brand_id:
        sales = sales.filter(battery__brand_id=brand_id)
    if amperage:
        sales = sales.filter(battery__amperage=amperage)

    # ۳. فیلتر تاریخ شمسی
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    if start_date:
        try:
            p = [int(x) for x in start_date.split('/')]
            sales = sales.filter(sale_date__gte=jdatetime.date(p[0], p[1], p[2]).togregorian())
        except ValueError:
            pass
    if end_date:
        try:
            p = [int(x) for x in end_date.split('/')]
            sales = sales.filter(sale_date__lte=jdatetime.date(p[0], p[1], p[2]).togregorian())
        except ValueError:
            pass

    brands = Brand.objects.all()
    # استخراج آمپرهای یکتا برای Dropdown فیلتر
    amperages = Battery.objects.values_list('amperage', flat=True).distinct()

    context = {
        'sales': sales,
        'brands': brands,
        'amperages': amperages,
        'search_query': search_query,
        'selected_brand': int(brand_id) if brand_id else '',
        'selected_amperage': amperage,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'sale_list.html', context)


@staff_member_required
def sale_detail_view(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    return render(request, 'sale_detail.html', {'sale': sale})


@staff_member_required
def sale_create_view(request):
  if request.method == 'POST':
    battery_id = request.POST.get('battery')
    customer_name = request.POST.get('customer_name')
    customer_phone = request.POST.get('customer_phone')
    warranty_serial = request.POST.get('warranty_serial')
    installer_id = request.POST.get('installer')

    # دریافت مبلغ تخفیف از فرم
    discount_raw = request.POST.get('discount', '0')
    try:
      discount_val = int(discount_raw) if discount_raw else 0
    except ValueError:
      discount_val = 0

    # ترکیب اجزای ۴ بخشی پلاک خودرو
    p1 = request.POST.get('plate_1', '').strip()
    p2 = request.POST.get('plate_2', '').strip()
    p3 = request.POST.get('plate_3', '').strip()
    p4 = request.POST.get('plate_4', '').strip()
    car_plate = f'{p1} {p2} {p3} - ایران {p4}' if (p1 and p3) else ''

    has_daghi = request.POST.get('has_daghi') == 'on'
    daghi_amperage = (
        request.POST.get('daghi_amperage', '') if has_daghi else None
    )

    if not battery_id or not warranty_serial:
      messages.error(
          request, 'لطفاً باتری و سریال گارانتی را الزماً وارد کنید.'
      )
    else:
      try:
        battery = Battery.objects.get(id=battery_id, status='available')
        installer_user = (
            User.objects.get(id=installer_id) if installer_id else None
        )

        # ثبت فاکتور به همراه تخفیف
        sale = Sale.objects.create(
            battery=battery,
            customer_name=customer_name,
            customer_phone=customer_phone,
            car_plate=car_plate,
            warranty_serial=warranty_serial,
            has_daghi=has_daghi,
            daghi_amperage=daghi_amperage,
            installer=installer_user,
            discount=discount_val,  # <--- اعمال تخفیف در اینجا
        )

        messages.success(request, 'فاکتور فروش با موفقیت ثبت شد.')
        return redirect('sale_list')

      except Exception as e:
        messages.error(request, f'خطا در ثبت فاکتور: {e}')

  available_batteries = Battery.objects.filter(
      status='available'
  ).select_related('brand')
  users = User.objects.all()
  daghi_choices = Sale.DAGHI_AMPERAGE_CHOICES

  context = {
      'available_batteries': available_batteries,
      'users': users,
      'daghi_choices': daghi_choices,
  }
  return render(request, 'sale_form.html', context)