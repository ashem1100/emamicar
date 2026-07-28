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

  # تعریف لیست انتخابی آمپرها
  AMPERAGE_CHOICES = (
      ("50L1", "50L1"),
      ("50L2", "50L2"),
      ("55", "55"),
      ("60", "60"),
      ("66", "66"),
      ("70", "70"),
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

  # متد کمکی برای استخراج مقدار عددی آمپر جهت محاسبات ریاضی (مثلا تبدیل 50L1 به عدد 50)
  @property
  def numeric_amperage(self):
      # رشته را تا قبل از حرف L برمی‌دارد (مثلا از 50L1 فقط 50 را جدا می‌کند)
      raw_amper = str(self.amperage).split('L')[0]
      digits = "".join(filter(str.isdigit, raw_amper))
      return int(digits) if digits else 0
  def save(self, *args, **kwargs):
    is_new = self.pk is None
    super().save(*args, **kwargs)

    # ساخت خودکار باتری‌های تکی
    if is_new:
      brand_code = self.brand.name[0].upper()
      for i in range(1, self.quantity + 1):
        short_code = (
            f"{self.invoice.invoice_number}-{brand_code}{self.amperage}-{i}"
        )

        # محاسبه قیمت خرید واقعی بر اساس عدد آمپر (مثلا ۵۰ * قیمت آمپری)
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
      PurchaseItem, on_delete=models.CASCADE, related_name="batteries",null=True
  )
  brand = models.ForeignKey(
      Brand, on_delete=models.PROTECT, verbose_name="برند"
  )
  amperage = models.CharField(max_length=10, verbose_name="آمپر")
  purchase_price = models.DecimalField(
      max_digits=12,
      decimal_places=0,
      verbose_name="قیمت خرید واقعی فاکتور (تومان)",
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

  # متد کمکی برای استخراج مقدار عددی آمپر
  @property
  def numeric_amperage(self):
      # رشته را تا قبل از حرف L برمی‌دارد (مثلا از 50L1 فقط 50 را جدا می‌کند)
      raw_amper = str(self.amperage).split('L')[0]
      digits = "".join(filter(str.isdigit, raw_amper))
      return int(digits) if digits else 0

  def __str__(self):
    return (
        f"{self.serial_code} | {self.brand.name} {self.amperage} -"
        f" {self.get_status_display()}"
    )


class Sale(models.Model):
  """ثبت فروش باتری"""

  battery = models.ForeignKey(
      Battery, on_delete=models.PROTECT, verbose_name="انتخاب باتری از انبار"
  )

  # اطلاعات مشتری
  customer_name = models.CharField(
      max_length=150, blank=True, null=True, verbose_name="نام مشتری"
  )
  customer_phone = models.CharField(
      max_length=20, blank=True, null=True, verbose_name="تلفن مشتری"
  )
  car_plate = models.CharField(
      max_length=50, blank=True, null=True, verbose_name="پلاک ماشین"
  )
  warranty_serial = models.CharField(
      max_length=100, verbose_name="سریال گارانتی"
  )

  # وضعیت داغی و نصاب
  has_daghi = models.BooleanField(default=True, verbose_name="تحویل داغی دارد؟")
  installer = models.ForeignKey(
      User,
      on_delete=models.SET_NULL,
      null=True,
      verbose_name="نصاب / فروشنده",
  )
  sale_date = models.DateField(default=timezone.now, verbose_name="تاریخ فروش")

  # فیلدهای مالی خودکار
  sale_price_without_daghi = models.DecimalField(
      max_digits=12,
      decimal_places=0,
      default=0,
      verbose_name="قیمت فروش روز بدون داغی",
  )
  daghi_discount = models.DecimalField(
      max_digits=12,
      decimal_places=0,
      default=0,
      verbose_name="مبلغ کسر شده داغی",
  )
  final_sale_price = models.DecimalField(
      max_digits=12,
      decimal_places=0,
      default=0,
      verbose_name="مبلغ نهایی دریافتی",
  )


  class Meta:
    verbose_name = "فروش باتری"
    verbose_name_plural = "فاکتورهای فروش"

  def save(self, *args, **kwargs):
    # ۱. خواندن تنظیمات کلی سیستم به صورت Decimal ایمن
    settings = SystemSetting.objects.last()
    daghi_rate = (
        Decimal(str(settings.daghi_price_per_amper))
        if settings
        else Decimal("40000")
    )
    profit_percent = (
        Decimal(str(settings.default_profit_percent))
        if settings
        else Decimal("20")
    )

    # ۲. خواندن نرخ روز فروش برند و آمپر عددی به صورت Decimal
    current_brand_rate = Decimal(
        str(self.battery.brand.selling_price_per_amper)
    )
    num_amperage = Decimal(str(self.battery.numeric_amperage))

    # ۳. محاسبه قیمت فروش پایه روز (آمپر × نرخ روز)
    base_price = num_amperage * current_brand_rate

    # ۴. قیمت فروش بدون داغی (با درصد سود) -> ضرب Decimal در Decimal
    profit_factor = Decimal("1") + (profit_percent / Decimal("100"))
    self.sale_price_without_daghi = base_price * profit_factor

    # ۵. محاسبه تخفیف داغی
    if self.has_daghi:
      self.daghi_discount = num_amperage * daghi_rate
    else:
      self.daghi_discount = Decimal("0")

    # ۶. مبلغ نهایی دریافتی از مشتری
    self.final_sale_price = self.sale_price_without_daghi - self.daghi_discount

    # ۷. سود واقعی (قیمت فروش بدون داغی منفی قیمت خرید اولیه)
    cost = (
        Decimal(str(self.battery.purchase_price))
        if self.battery.purchase_price
        else Decimal("0")
    )
    self.profit = self.sale_price_without_daghi - cost

    is_new = self.pk is None
    super().save(*args, **kwargs)

    if is_new:
      self.battery.status = "sold"
      self.battery.save()