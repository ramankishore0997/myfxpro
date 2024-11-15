import datetime

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin, Group, Permission
from django.db import models
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class KYC(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    aadhar_number = models.CharField(max_length=12)
    pan_number = models.CharField(max_length=10)
    aadhar_front = models.ImageField(upload_to='kyc_docs/aadhar_front/')
    aadhar_back = models.ImageField(upload_to='kyc_docs/aadhar_back/')
    pan_front = models.ImageField(upload_to='kyc_docs/pan_front/')
    pan_back = models.ImageField(upload_to='kyc_docs/pan_back/')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"KYC for {self.user.email} - {self.status}"


class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    # New fields
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    full_name = models.CharField(max_length=255, blank=True, null=True)
    pan_card_number = models.CharField(max_length=10, blank=True, null=True)
    # Assuming this is part of your CustomUser model in models.py
    kyc_status = models.CharField(max_length=10, choices=KYC.STATUS_CHOICES, default='pending')

    open_trades = models.IntegerField(default=0)
    transactions = models.IntegerField(default=0)

    # Email Verification
    is_verified = models.BooleanField(default=False)
    token = models.TextField(null=True, blank=True)

    # Specify related_name to avoid conflict with auth.User model
    groups = models.ManyToManyField(
        Group,
        related_name="customuser_set",
        blank=True,
        help_text="The groups this user belongs to.",
        verbose_name="groups"
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name="customuser_set",
        blank=True,
        help_text="Specific permissions for this user.",
        verbose_name="user permissions"
    )

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email


class DepositOption(models.Model):
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_link = models.URLField()

    def __str__(self):
        return f"Deposit {self.amount}"


class WithdrawalRequest(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_processed = models.BooleanField(default=False)
    request_date = models.DateTimeField(auto_now_add=True)
    is_rejected = models.BooleanField(default=False)  # New field for rejection status
    rejection_reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user} - ₹{self.amount}"


class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
    ]
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.transaction_type} - ₹{self.amount}"


class DepositRequest(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('UPI', 'UPI'),
        ('USDT', 'USDT'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES)
    upi_id = models.CharField(max_length=50, blank=True, null=True)
    crypto_address = models.CharField(max_length=100, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_processed = models.BooleanField(default=False)
    request_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.method} - {self.amount}"


class Trade(models.Model):
    FOREX_PAIRS = [
        ('EURUSD', 'EUR/USD'),
        ('GBPUSD', 'GBP/USD'),
        ('USDJPY', 'USD/JPY'),
        ('AUDUSD', 'AUD/USD'),
        ('USDCAD', 'USD/CAD'),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)  # User making the trade
    forex_pair = models.CharField(max_length=6, choices=FOREX_PAIRS)  # Forex pair traded
    amount = models.DecimalField(max_digits=10, decimal_places=2)  # Amount involved in the trade
    profit = models.DecimalField(max_digits=10, decimal_places=2)  # Profit or loss from the trade
    trade_time = models.DateTimeField(default=datetime.datetime.now())  # Time when the trade was made
    entry_price = models.DecimalField(max_digits=10, decimal_places=5)  # Entry price of the trade
    exit_price = models.DecimalField(max_digits=10, decimal_places=5)  # Exit price of the trade
    status = models.CharField(max_length=10, default='closed')  # Status of the trade (e.g., 'closed', 'open')

    def __str__(self):
        return f"{self.forex_pair} - {self.amount} - {self.profit} - {self.trade_time}"

    def is_profitable(self):
        """Method to check if the trade was profitable."""
        return self.profit > 0


class CrptoId(models.Model):
    cry_id = models.TextField(max_length=255)


