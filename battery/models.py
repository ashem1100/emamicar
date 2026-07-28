from django.db import models
from django.utils import timezone


class Purchase(models.Model):
  """مدل فاکتور خرید (بار جدید)"""

  invoice_number = models.CharField(
      max_length=50, unique=True, verbose_name="شماره فاکتور خرید"
  )
  brand = models.CharField(max_length=100, verbose_name="برند باتری")
  amperage = models.IntegerField(verbose_name="آمپر باتری")
  quantity = models.IntegerField(verbose_name="تعداد خریداری شده")
  purchase_price_per_amper = models.DecimalField(
      max_digits=12, decimal_places=2, verbose_name="قیمت خرید هر آمپر"
  )
  date_purchased = models.DateTimeField(
      default=timezone.now, verbose_name="تاریخ خرید"
  )

  def __str__(self):
    return (
        f"فاکتور {self.invoice_number} - {self.brand} {self.amperage} آمپر (تعداد:"
        f" {self.quantity})"
    )

  def save(self, *args, **kwargs):
    # چک می‌کنیم که آیا این خرید تازه ایجاد شده یا در حال ویرایش است
    is_new = self.pk is None
    super().save(*args, **kwargs)  # اول خود فاکتور خرید ذخیره می‌شود

    # اگر خرید جدید باشد، به تعدادِ `quantity` باتری تکی با کد اختصاصی می‌سازیم
    if is_new:
      for i in range(1, self.quantity + 1):
        # تولید یک کد یا سریال یکتا برای هر باتری (مثلا: شماره فاکتور + شماره ترتیب)
        unique_serial = f"{self.invoice_number}-{self.amperage}-{i}"

        Battery.objects.create(
            purchase=self,
            brand=self.brand,
            amperage=self.amperage,
            purchase_price_per_amper=self.purchase_price_per_amper,
            serial_code=unique_serial,
            status="available",
        )


class Battery(models.Model):
  """مدل باتری‌های تکی (هر باتری یک کد یکتا دارد و به فاکتور خرید وصل است)"""

  STATUS_CHOICES = (
      ("available", "موجود در انبار"),
      ("sold", "فروخته شده"),
      ("returned", "مرجوعی"),
  )

  purchase = models.ForeignKey(
      Purchase,
      on_delete=models.CASCADE,
      related_name="batteries",
      verbose_name="فاکتور خرید مربوطه",
  )
  brand = models.CharField(max_length=100, verbose_name="برند باتری")
  amperage = models.IntegerField(verbose_name="آمپر")
  purchase_price_per_amper = models.DecimalField(
      max_digits=12, decimal_places=2, verbose_name="قیمت خرید هر آمپر"
  )
  serial_code = models.CharField(
      max_length=100, unique=True, verbose_name="کد/سریال اختصاصی باتری"
  )
  status = models.CharField(
      max_length=20,
      choices=STATUS_CHOICES,
      default="available",
      verbose_name="وضعیت",
  )

  def __str__(self):
    return (
        f"{self.brand} ({self.amperage} آمپر) - کد: {self.serial_code} -"
        f" {self.get_status_display()}"
    )


class Sale(models.Model):
  """مدل فروش باتری (هر فروش شامل یک باتری است)"""

  # ارتباط با باتری تکی انبار (با انتخاب این باتری، کد، برند و آمپر مشخص می‌شود)
  battery = models.ForeignKey(
      "Battery",
      on_delete=models.PROTECT,
      verbose_name="کد/سریال باتری فروخته شده",
  )

  # اطلاعات مشتری
  customer_name = models.CharField(
      max_length=150, blank=True, null=True, verbose_name="نام مشتری"
  )
  customer_phone = models.CharField(
      max_length=20, blank=True, null=True, verbose_name="شماره تلفن مشتری"
  )
  car_plate = models.CharField(
      max_length=50, blank=True, null=True, verbose_name="پلاک ماشین"
  )

  # سریال گارانتی که خودتان دستی وارد می‌کنید
  warranty_serial = models.CharField(
      max_length=100, verbose_name="سریال گارانتی"
  )

  # اطلاعات مالی و نصاب
  daghi_price = models.DecimalField(
      max_digits=15,
      decimal_places=2,
      default=0,
      verbose_name="مبلغ داغی تحویل گرفته شده (تومان)",
  )
  installer_name = models.CharField(
      max_length=100, blank=True, null=True, verbose_name="نام شخص نصاب"
  )

  # تاریخ فروش
  sale_date = models.DateTimeField(default=timezone.now, verbose_name="تاریخ فروش")

  def __str__(self):
    return (
        f"فروش باتری {self.battery.serial_code} به"
        f" {self.customer_name or 'مشتری'}"
    )

  def save(self, *args, **kwargs):
      is_new = self.pk is None
      super().save(*args, **kwargs)

      # اگر فروش جدید ثبت شد، وضعیت باتری را به 'فروخته شده' تغییر بده
      if is_new:
          self.battery.status = "sold"
          self.battery.save()

  # خاصیت کمکی برای دسترسی سریع به برند و آمپر از روی باتری
  @property
  def battery_brand(self):
    return self.battery.brand

  @property
  def battery_amperage(self):
    return self.battery.amperage