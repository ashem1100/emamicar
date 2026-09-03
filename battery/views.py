from datetime import timedelta
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.db.models import Count, Sum, Q, DecimalField
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from .models import *
import json
from django.db.models.functions import ExtractMonth
from django.http import JsonResponse
import jdatetime
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from collections import defaultdict
from django.db.models.functions import Coalesce
from decimal import Decimal
from django.views.decorators.http import require_POST
import uuid


@staff_member_required
def dashboard_view(request):
    period = request.GET.get('period', 'all')
    now = timezone.now().date()

    sales_queryset = Sale.objects.all()

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

    available_batteries = Battery.objects.filter(status='available')
    total_available_count = available_batteries.count()

    inventory_summary = (
        available_batteries.values('brand__name', 'amperage')
        .annotate(count=Count('id'))
        .order_by('brand__name', 'amperage')
    )

    sales_with_daghi = sales_queryset.filter(has_daghi=True)
    total_daghi_count = sales_with_daghi.count()

    total_daghi_amperage = sum(
        sale.numeric_daghi_amperage for sale in sales_with_daghi
    )

    total_sales_count = sales_queryset.count()
    total_sales_amount = (
            sales_queryset.aggregate(Sum('final_sale_price'))['final_sale_price__sum']
            or 0
    )

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

    brand_sales = (
        sales_queryset.values('battery__brand__name')
        .annotate(total_count=Count('id'))
        .order_by('-total_count')
    )
    brand_labels = [item['battery__brand__name'] for item in brand_sales]
    brand_counts = [item['total_count'] for item in brand_sales]

    amper_sales = (
        sales_queryset.values('battery__amperage')
        .annotate(total_count=Count('id'))
        .order_by('-total_count')
    )
    amper_labels = [f"{item['battery__amperage']} آمپر" for item in amper_sales]
    amper_counts = [item['total_count'] for item in amper_sales]

    shamsi_months = [
        'فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
        'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند',
    ]

    monthly_data = defaultdict(float)

    for sale in sales_queryset:
        if sale.sale_date:
            j_date = jdatetime.date.fromgregorian(date=sale.sale_date)
            month_key = (j_date.month, shamsi_months[j_date.month - 1])
            monthly_data[month_key] += float(sale.final_sale_price or 0)

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

    search_query = request.GET.get('search', '')
    if search_query:
        sales = sales.filter(
            Q(customer_name__icontains=search_query) |
            Q(customer_phone__icontains=search_query) |
            Q(car_plate__icontains=search_query) |
            Q(car_model__icontains=search_query) |
            Q(battery__serial_code__icontains=search_query)
        )

    brand_id = request.GET.get('brand', '')
    amperage = request.GET.get('amperage', '')
    if brand_id:
        sales = sales.filter(battery__brand_id=brand_id)
    if amperage:
        sales = sales.filter(battery__amperage=amperage)

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
        payment_method_id = request.POST.get('payment_method')

        date_str = request.POST.get('sale_date')
        warranty_end_date_str = request.POST.get('warranty_end_date')

        car_model = request.POST.get('car_model')

        # دریافت تخفیف
        discount_raw = request.POST.get('discount', '0')
        try:
            discount_clean = "".join(filter(str.isdigit, str(discount_raw)))
            discount_val = Decimal(discount_clean) if discount_clean else Decimal('0')
        except Exception:
            discount_val = Decimal('0')

        # دریافت اضافه‌بها
        surcharge_raw = request.POST.get('surcharge', '0')
        try:
            surcharge_clean = "".join(filter(str.isdigit, str(surcharge_raw)))
            surcharge_val = Decimal(surcharge_clean) if surcharge_clean else Decimal('0')
        except Exception:
            surcharge_val = Decimal('0')

        # دریافت قیمت نهایی
        final_price_raw = request.POST.get('final_price', '')
        try:
            final_price_clean = "".join(filter(str.isdigit, str(final_price_raw)))
            final_price_val = Decimal(final_price_clean) if final_price_clean else None
        except Exception:
            final_price_val = None

        # اعتبارسنجی پلاک اختیاری
        p1 = request.POST.get('plate_1', '').strip()
        p2 = request.POST.get('plate_2', '').strip()
        p3 = request.POST.get('plate_3', '').strip()
        p4 = request.POST.get('plate_4', '').strip()

        if any([p1, p2, p3, p4]):
            main_parts = " ".join([part for part in [p1, p2, p3] if part])
            iran_part = f" - ایران {p4}" if p4 else ""
            car_plate = f"{main_parts}{iran_part}".strip()
        else:
            car_plate = None

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
                # تبدیل تاریخ فروش
                if date_str:
                    try:
                        parts = [int(x) for x in date_str.split('/')]
                        sale_date = jdatetime.date(parts[0], parts[1], parts[2]).togregorian()
                    except Exception:
                        sale_date = timezone.now().date()
                else:
                    sale_date = timezone.now().date()

                # تبدیل تاریخ پایان گارانتی
                warranty_end_date = None
                if warranty_end_date_str:
                    try:
                        w_parts = [int(x) for x in warranty_end_date_str.split('/')]
                        warranty_end_date = jdatetime.date(w_parts[0], w_parts[1], w_parts[2]).togregorian()
                    except Exception:
                        pass

                battery = Battery.objects.get(id=battery_id, status='available')
                installer_user = User.objects.get(id=installer_id) if installer_id else None
                payment_method_obj = PaymentMethod.objects.get(id=payment_method_id) if payment_method_id else None

                sale = Sale.objects.create(
                    battery=battery,
                    customer_name=customer_name,
                    customer_phone=customer_phone,
                    car_plate=car_plate,
                    car_model=car_model,
                    warranty_serial=warranty_serial,
                    warranty_end_date=warranty_end_date,
                    has_daghi=has_daghi,
                    daghi_amperage=daghi_amperage,
                    installer=installer_user,
                    discount=discount_val,
                    surcharge=surcharge_val,
                    payment_method=payment_method_obj,
                    sale_date=sale_date,
                    **({"final_sale_price": final_price_val} if final_price_val is not None else {}),
                )

                messages.success(request, 'فاکتور فروش با موفقیت ثبت شد.')
                return redirect('sale_list')

            except Exception as e:
                messages.error(request, f'خطا در ثبت فاکتور: {e}')

    available_batteries = Battery.objects.filter(status='available').select_related('brand')
    users = User.objects.all()
    daghi_choices = Sale.DAGHI_AMPERAGE_CHOICES
    payment_methods = PaymentMethod.objects.filter(is_active=True)
    settings = SystemSetting.objects.last()

    today_jalali = jdatetime.date.today().strftime('%Y/%m/%d')

    context = {
        'available_batteries': available_batteries,
        'users': users,
        'daghi_choices': daghi_choices,
        'payment_methods': payment_methods,
        'settings': settings,
        'today_jalali': today_jalali,
        'brands': Brand.objects.all(),
    }
    return render(request, 'sale_form.html', context)


@login_required
def installer_dashboard_view(request):
    """داشبورد اختصاصی نصاب به همراه آمار فروش‌های اخیر"""
    my_sales = Sale.objects.filter(installer=request.user).select_related('battery', 'battery__brand').order_by(
        '-sale_date')
    context = {
        'my_sales': my_sales,
    }
    return render(request, 'installer_dashboard.html', context)


@login_required
def installer_sale_create_view(request):
    if request.method == 'POST':
        battery_id = request.POST.get('battery')
        customer_name = request.POST.get('customer_name')
        customer_phone = request.POST.get('customer_phone')
        warranty_serial = request.POST.get('warranty_serial')
        payment_method_id = request.POST.get('payment_method')

        date_str = request.POST.get('sale_date')
        warranty_end_date_str = request.POST.get('warranty_end_date')

        car_model = request.POST.get('car_model')

        # دریافت تخفیف
        discount_raw = request.POST.get('discount', '0')
        try:
            discount_clean = "".join(filter(str.isdigit, str(discount_raw)))
            discount_val = Decimal(discount_clean) if discount_clean else Decimal('0')
        except Exception:
            discount_val = Decimal('0')

        # دریافت اضافه‌بها
        surcharge_raw = request.POST.get('surcharge', '0')
        try:
            surcharge_clean = "".join(filter(str.isdigit, str(surcharge_raw)))
            surcharge_val = Decimal(surcharge_clean) if surcharge_clean else Decimal('0')
        except Exception:
            surcharge_val = Decimal('0')

        # دریافت قیمت نهایی
        final_price_raw = request.POST.get('final_price', '')
        try:
            final_price_clean = "".join(filter(str.isdigit, str(final_price_raw)))
            final_price_val = Decimal(final_price_clean) if final_price_clean else None
        except Exception:
            final_price_val = None

        # اعتبارسنجی پلاک اختیاری
        p1 = request.POST.get('plate_1', '').strip()
        p2 = request.POST.get('plate_2', '').strip()
        p3 = request.POST.get('plate_3', '').strip()
        p4 = request.POST.get('plate_4', '').strip()

        if any([p1, p2, p3, p4]):
            main_parts = " ".join([part for part in [p1, p2, p3] if part])
            iran_part = f" - ایران {p4}" if p4 else ""
            car_plate = f"{main_parts}{iran_part}".strip()
        else:
            car_plate = None

        has_daghi = request.POST.get('has_daghi') == 'on'
        daghi_amperage = request.POST.get('daghi_amperage', '') if has_daghi else None

        if not battery_id or not warranty_serial:
            messages.error(request, 'لطفاً باتری و سریال گارانتی را الزماً وارد کنید.')
        else:
            try:
                # تبدیل تاریخ فروش
                if date_str:
                    try:
                        parts = [int(x) for x in date_str.split('/')]
                        sale_date = jdatetime.date(parts[0], parts[1], parts[2]).togregorian()
                    except Exception:
                        sale_date = timezone.now().date()
                else:
                    sale_date = timezone.now().date()

                # تبدیل تاریخ پایان گارانتی
                warranty_end_date = None
                if warranty_end_date_str:
                    try:
                        w_parts = [int(x) for x in warranty_end_date_str.split('/')]
                        warranty_end_date = jdatetime.date(w_parts[0], w_parts[1], w_parts[2]).togregorian()
                    except Exception:
                        pass

                battery = Battery.objects.get(id=battery_id, status='available')
                installer_user = request.user
                payment_method_obj = PaymentMethod.objects.get(id=payment_method_id) if payment_method_id else None

                Sale.objects.create(
                    battery=battery,
                    customer_name=customer_name,
                    customer_phone=customer_phone,
                    car_plate=car_plate,
                    car_model=car_model,
                    warranty_serial=warranty_serial,
                    warranty_end_date=warranty_end_date,
                    has_daghi=has_daghi,
                    daghi_amperage=daghi_amperage,
                    installer=installer_user,
                    discount=discount_val,
                    surcharge=surcharge_val,
                    payment_method=payment_method_obj,
                    sale_date=sale_date,
                    **({"final_sale_price": final_price_val} if final_price_val is not None else {}),
                )

                messages.success(request, 'فاکتور فروش با موفقیت در پنل شما ثبت شد.')
                return redirect('installer_dashboard')

            except Exception as e:
                messages.error(request, f'خطا در ثبت فاکتور: {e}')

    available_batteries = Battery.objects.filter(status='available').select_related('brand')
    daghi_choices = Sale.DAGHI_AMPERAGE_CHOICES
    payment_methods = PaymentMethod.objects.filter(is_active=True)
    settings = SystemSetting.objects.last()
    today_jalali = jdatetime.date.today().strftime('%Y/%m/%d')

    context = {
        'available_batteries': available_batteries,
        'daghi_choices': daghi_choices,
        'payment_methods': payment_methods,
        'settings': settings,
        'today_jalali': today_jalali,
    }
    return render(request, 'installer_sale_form.html', context)


@login_required
def installer_sale_list_view(request):
    my_sales = (
        Sale.objects.filter(installer=request.user)
        .select_related('battery', 'battery__brand')
        .order_by('-sale_date')
    )

    search_query = request.GET.get('search', '').strip()
    if search_query:
        my_sales = my_sales.filter(
            Q(customer_name__icontains=search_query)
            | Q(customer_phone__icontains=search_query)
            | Q(car_plate__icontains=search_query)
            | Q(car_model__icontains=search_query)
            | Q(battery__serial_code__icontains=search_query)
        )

    brand_id = request.GET.get('brand', '')
    amperage = request.GET.get('amperage', '')
    if brand_id:
        my_sales = my_sales.filter(battery__brand_id=brand_id)
    if amperage:
        my_sales = my_sales.filter(battery__amperage=amperage)

    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()

    if start_date:
        try:
            p = [int(x) for x in start_date.split('/')]
            my_sales = my_sales.filter(
                sale_date__gte=jdatetime.date(p[0], p[1], p[2]).togregorian()
            )
        except (ValueError, IndexError):
            pass

    if end_date:
        try:
            p = [int(x) for x in end_date.split('/')]
            my_sales = my_sales.filter(
                sale_date__lte=jdatetime.date(p[0], p[1], p[2]).togregorian()
            )
        except (ValueError, IndexError):
            pass

    brands = Brand.objects.all()
    amperages = Battery.objects.values_list('amperage', flat=True).distinct()

    context = {
        'my_sales': my_sales,
        'brands': brands,
        'amperages': amperages,
        'search_query': search_query,
        'selected_brand': int(brand_id) if brand_id.isdigit() else '',
        'selected_amperage': amperage,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'installer_sale_list.html', context)


@staff_member_required
def installer_management_view(request):
    users = User.objects.annotate(
        total_earned=Coalesce(
            Sum(
                'transactions__amount',
                filter=Q(transactions__transaction_type='earn'),
            ),
            Decimal('0'),
            output_field=DecimalField(),
        ),
        total_payout=Coalesce(
            Sum(
                'transactions__amount',
                filter=Q(transactions__transaction_type='payout'),
            ),
            Decimal('0'),
            output_field=DecimalField(),
        ),
    ).order_by('username')

    installers_data = []
    for u in users:
        balance = (u.total_earned or Decimal('0')) - (
                u.total_payout or Decimal('0')
        )
        installers_data.append({
            'user': u,
            'total_earned': u.total_earned,
            'total_payout': u.total_payout,
            'balance': balance,
        })

    return render(
        request, 'installer_management.html', {'installers': installers_data}
    )


@staff_member_required
def installer_payout_view(request, user_id):
    installer = get_object_or_404(User, id=user_id)

    earned = (
            InstallerTransaction.objects.filter(installer=installer, transaction_type='earn').aggregate(
                s=Sum('amount'))['s']
            or 0
    )
    payout = (
            InstallerTransaction.objects.filter(installer=installer, transaction_type='payout').aggregate(
                s=Sum('amount'))['s']
            or 0
    )
    balance = earned - payout

    if request.method == 'POST':
        amount = request.POST.get('amount')
        description = request.POST.get('description', 'تسویه حساب')
        date_str = request.POST.get('date')

        try:
            p = [int(x) for x in date_str.split('/')]
            g_date = jdatetime.date(p[0], p[1], p[2]).togregorian()

            InstallerTransaction.objects.create(
                installer=installer,
                transaction_type='payout',
                amount=amount,
                description=description,
                date=g_date
            )
            messages.success(request, f'مبلغ {amount} تومان با موفقیت برای {installer.get_full_name()} تسویه شد.')
            return redirect('installer_management')
        except Exception as e:
            messages.error(request, f'خطا در ثبت تسویه: {e}')

    context = {
        'installer': installer,
        'balance': balance,
        'today': jdatetime.date.today().strftime('%Y/%m/%d')
    }
    return render(request, 'installer_payout.html', context)


@login_required
def installer_wallet_view(request):
    transactions = InstallerTransaction.objects.filter(installer=request.user).order_by('-date', '-id')

    earned = transactions.filter(transaction_type='earn').aggregate(s=Sum('amount'))['s'] or 0
    payout = transactions.filter(transaction_type='payout').aggregate(s=Sum('amount'))['s'] or 0
    balance = earned - payout

    context = {
        'transactions': transactions,
        'balance': balance,
        'total_earned': earned,
        'total_payout': payout
    }
    return render(request, 'installer_wallet.html', context)


@staff_member_required
@require_POST
def quick_add_battery_view(request):
    try:
        data = json.loads(request.body)

        brand_id = data.get('brand_id')
        amperage = data.get('amperage', '').strip()

        if not brand_id or not amperage:
            return JsonResponse(
                {'success': False, 'error': 'برند و آمپر الزامی هستند.'},
                status=400
            )

        brand = Brand.objects.get(pk=brand_id)

        short_uuid = uuid.uuid4().hex[:6].upper()
        brand_code = brand.name[0].upper()
        serial_code = f"QUICK-{brand_code}{amperage}-{short_uuid}"

        while Battery.objects.filter(serial_code=serial_code).exists():
            short_uuid = uuid.uuid4().hex[:6].upper()
            serial_code = f"QUICK-{brand_code}{amperage}-{short_uuid}"

        battery = Battery.objects.create(
            brand=brand,
            amperage=amperage,
            purchase_price=None,
            serial_code=serial_code,
            status='available',
        )

        return JsonResponse({
            'success': True,
            'battery': {
                'id': battery.pk,
                'label': str(battery),
                'numeric_amperage': battery.numeric_amperage,
                'brand_rate': str(brand.selling_price_per_amper),
            }
        })

    except Brand.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'برند پیدا نشد.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
