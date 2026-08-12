from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from decimal import Decimal


class SystemSetting(models.Model):
    """تنظیمات کلی سیستم (قیمت روز داغی و درصد سود)"""

    daghi_price_per_amper = models.DecimalField(
        max_digits=10, decimal_places=0, verbose_name="قیمت خرید روز داغی (هر آمپر)"
    )
    default_profit_percent = models.IntegerField(
        default=20, verbose_name="درصد سود پیش‌فرض فروش"
    )
    installation_fee = models.DecimalField(
        max_digits=10, decimal_places=0, default=250000,
        verbose_name="اجرت نصب پایه (تومان)"
    )

    class Meta:
        verbose_name = "تنظیمات قیمت داغی و سود"
        verbose_name_plural = "تنظیمات پایه سیستم"

    def __str__(self):
        return (
            f"نرخ داغی: {self.daghi_price_per_amper:,} تومان | سود:"
            f" {self.default_profit_percent}٪"
        )


class Brand(models.Model):
    """جدول برندهای باتری (با قیمت روز فروش هر آمپر)"""

    name = models.CharField(max_length=100, unique=True, verbose_name="نام برند")
    selling_price_per_amper = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        default=0,
        verbose_name="قیمت فروش روز هر آمپر (تومان)",
    )

    class Meta:
        verbose_name = "برند باتری"
        verbose_name_plural = "برندها"

    def __str__(self):
        return f"{self.name} (نرخ روز: {self.selling_price_per_amper:,} تومان)"


class PurchaseInvoice(models.Model):
    """فاکتور اصلی خرید"""

    invoice_number = models.CharField(
        max_length=50, unique=True, verbose_name="شماره فاکتور خرید"
    )
    date_purchased = models.DateField(
        default=timezone.now, verbose_name="تاریخ خرید"
    )
    description = models.TextField(
        blank=True, null=True, verbose_name="توضیحات"
    )

    class Meta:
        verbose_name = "فاکتور خرید"
        verbose_name_plural = "فاکتورهای خرید"

    def __str__(self):
        return f"فاکتور {self.invoice_number}"


class PurchaseItem(models.Model):
    """آیتم‌های فاکتور خرید"""

    AMPERAGE_CHOICES = (
        ("50L1", "50L1"),
        ("50L2", "50L2"),
        ("55", "55"),
        ("60", "60"),
        ("66", "66"),
        ("70L", "70L"),
        ("70R", "70R"),
        ("74", "74"),
    )

    invoice = models.ForeignKey(
        PurchaseInvoice,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="فاکتور",
    )
    brand = models.ForeignKey(
        Brand, on_delete=models.PROTECT, verbose_name="برند"
    )
    amperage = models.CharField(
        max_length=10,
        choices=AMPERAGE_CHOICES,
        default="50L1",
        verbose_name="آمپر",
    )
    quantity = models.IntegerField(verbose_name="تعداد")
    purchase_price_per_amper = models.DecimalField(
        max_digits=10, decimal_places=0, verbose_name="قیمت خرید هر آمپر (تومان)"
    )

    class Meta:
        verbose_name = "آیتم خرید"
        verbose_name_plural = "آیتم‌های خرید"

    @property
    def numeric_amperage(self):
        raw_amper = str(self.amperage).split('L')[0].split('R')[0]
        digits = "".join(filter(str.isdigit, raw_amper))
        return int(digits) if digits else 0

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new:
            brand_code = self.brand.name[0].upper()
            for i in range(1, self.quantity + 1):
                short_code = (
                    f"{self.invoice.invoice_number}-{brand_code}{self.amperage}-{i}"
                )
                unit_purchase_price = (
                        self.numeric_amperage * self.purchase_price_per_amper
                )
                Battery.objects.create(
                    purchase_item=self,
                    brand=self.brand,
                    amperage=self.amperage,
                    purchase_price=unit_purchase_price,
                    serial_code=short_code,
                    status="available",
                )


class Battery(models.Model):
    """باتری‌های تکی انبار"""

    STATUS_CHOICES = (
        ("available", "موجود در انبار"),
        ("sold", "فروخته شده"),
    )

    purchase_item = models.ForeignKey(
        PurchaseItem, on_delete=models.CASCADE, related_name="batteries", null=True, blank=True
    )
    brand = models.ForeignKey(
        Brand, on_delete=models.PROTECT, verbose_name="برند"
    )
    amperage = models.CharField(max_length=10, verbose_name="آمپر")
    purchase_price = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        verbose_name="قیمت خرید واقعی فاکتور (تومان)",
        blank=True,
        null=True
    )
    serial_code = models.CharField(
        max_length=50, unique=True, verbose_name="کد کوتاه باتری"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="available",
        verbose_name="وضعیت",
    )

    class Meta:
        verbose_name = "باتری انبار"
        verbose_name_plural = "موجودی باتری‌ها"

    @property
    def numeric_amperage(self):
        raw_amper = str(self.amperage).split('L')[0].split('R')[0]
        digits = "".join(filter(str.isdigit, raw_amper))
        return int(digits) if digits else 0

    def __str__(self):
        return (
            f"{self.serial_code} | {self.brand.name} {self.amperage} -"
            f" {self.get_status_display()}"
        )


class PaymentMethod(models.Model):
    """مدیریت روش‌های پرداخت از طریق ادمین"""
    name = models.CharField(max_length=100, verbose_name="روش پرداخت (مثل: کارتخوان، نقدی)")
    is_active = models.BooleanField(default=True, verbose_name="وضعیت فعال")

    class Meta:
        verbose_name = "روش پرداخت"
        verbose_name_plural = "روش‌های پرداخت"

    def __str__(self):
        return self.name


class Sale(models.Model):
    """ثبت فروش باتری"""

    DAGHI_AMPERAGE_CHOICES = (
        ('50', '50 آمپر'),
        ('55', '55 آمپر'),
        ('60', '60 آمپر'),
        ('66', '66 آمپر'),
        ('70', '70 آمپر'),
        ('74', '74 آمپر'),
        ('90', '90 آمپر'),
        ('100', '100 آمپر'),
    )

    battery = models.ForeignKey(
        Battery, on_delete=models.PROTECT, verbose_name='انتخاب باتری از انبار'
    )

    customer_name = models.CharField(
        max_length=150, blank=True, null=True, verbose_name='نام مشتری'
    )
    customer_phone = models.CharField(
        max_length=20, blank=True, null=True, verbose_name='تلفن مشتری'
    )
    car_plate = models.CharField(
        max_length=50, blank=True, null=True, verbose_name='پلاک ماشین'
    )

    # فیلد جدید اضافه شده: مدل ماشین
    car_model = models.CharField(
        max_length=100, blank=True, null=True, verbose_name='مدل ماشین'
    )

    warranty_serial = models.CharField(
        max_length=100, verbose_name='سریال گارانتی'
    )

    has_daghi = models.BooleanField(default=True, verbose_name='تحویل داغی دارد؟')
    daghi_amperage = models.CharField(
        max_length=10,
        choices=DAGHI_AMPERAGE_CHOICES,
        blank=True,
        null=True,
        verbose_name='آمپر داغی تحویلی (در صورت متفاوت بودن)',
        help_text=(
            'اگر خالی بماند، به صورت خودکار برابر با آمپر باتری نو محاسبه'
            ' می‌شود.'
        ),
    )

    installer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='نصاب / فروشنده',
    )
    sale_date = models.DateField(default=timezone.now, verbose_name='تاریخ فروش')

    discount = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=Decimal('0'),
        verbose_name='مبلغ تخفیف (تومان)',
        help_text='مبلغ تخفیفی که دستی از فاکتور کسر می‌شود',
    )

    sale_price_without_daghi = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        verbose_name='قیمت فروش روز بدون داغی',
    )
    daghi_discount = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        verbose_name='مبلغ کسر شده داغی',
    )
    final_sale_price = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        verbose_name='مبلغ نهایی دریافتی',
    )
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='روش پرداخت'
    )

    class Meta:
        verbose_name = 'فروش باتری'
        verbose_name_plural = 'فاکتورهای فروش'

    @property
    def formatted_plate_parts(self):
        if not self.car_plate:
            return None
        try:
            parts = self.car_plate.split(' - ایران ')
            main_part = parts[0].strip().split(' ')
            iran_code = parts[1].strip() if len(parts) > 1 else ''
            return {
                'p1': main_part[0] if len(main_part) > 0 else '',
                'p2': main_part[1] if len(main_part) > 1 else '',
                'p3': main_part[2] if len(main_part) > 2 else '',
                'iran': iran_code,
            }
        except Exception:
            return None

    @property
    def numeric_daghi_amperage(self):
        if self.daghi_amperage:
            digits = ''.join(filter(str.isdigit, str(self.daghi_amperage)))
            return int(digits) if digits else self.battery.numeric_amperage
        return self.battery.numeric_amperage

    @property
    def profit(self):
        cost = (
            Decimal(str(self.battery.purchase_price))
            if self.battery.purchase_price
            else Decimal('0')
        )
        return self.sale_price_without_daghi - cost

    def save(self, *args, **kwargs):
        settings = SystemSetting.objects.last()
        daghi_rate = (
            Decimal(str(settings.daghi_price_per_amper))
            if settings
            else Decimal('40000')
        )
        profit_percent = (
            Decimal(str(settings.default_profit_percent))
            if settings
            else Decimal('20')
        )

        current_brand_rate = Decimal(
            str(self.battery.brand.selling_price_per_amper)
        )
        new_battery_amperage = Decimal(str(self.battery.numeric_amperage))
        base_price = new_battery_amperage * current_brand_rate

        profit_factor = Decimal('1') + (profit_percent / Decimal('100'))
        self.sale_price_without_daghi = base_price * profit_factor

        if self.has_daghi:
            actual_daghi_amper = Decimal(str(self.numeric_daghi_amperage))
            self.daghi_discount = actual_daghi_amper * daghi_rate
        else:
            self.daghi_discount = Decimal('0')

        manual_discount = self.discount or Decimal('0')
        calculated_final = (
                self.sale_price_without_daghi - self.daghi_discount - manual_discount
        )
        self.final_sale_price = max(Decimal('0'), calculated_final)

        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new:
            self.battery.status = 'sold'
            self.battery.save()

            if self.installer:
                settings = SystemSetting.objects.last()
                fee_amount = settings.installation_fee if settings else Decimal('250000')

                if fee_amount > 0:
                    InstallerTransaction.objects.create(
                        installer=self.installer,
                        transaction_type='earn',
                        amount=fee_amount,
                        sale=self,
                        description=f'اجرت نصب فاکتور شماره {self.id} (پلاک: {self.car_plate})'
                    )


class InstallerTransaction(models.Model):
    TRANSACTION_TYPES = (
        ('earn', 'درآمد اجرت (بستانکار)'),
        ('payout', 'تسویه حساب (بدهکار)'),
    )

    installer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions', verbose_name="نصاب")
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES, verbose_name="نوع تراکنش")
    amount = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="مبلغ (تومان)")
    sale = models.ForeignKey('Sale', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="بابت فاکتور")
    description = models.CharField(max_length=255, blank=True, null=True, verbose_name="توضیحات")
    date = models.DateField(default=timezone.now, verbose_name="تاریخ تراکنش")

    class Meta:
        verbose_name = "تراکنش نصاب"
        verbose_name_plural = "کیف پول نصاب‌ها"

    def __str__(self):
        return f"{self.installer.username} - {self.get_transaction_type_display()} - {self.amount}"