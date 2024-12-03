from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import *


class CustomerUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('email', 'balance', 'is_staff', 'is_active', 'token')  # Added 'balance' here
    list_filter = ('is_staff', 'is_active')
    search_fields = ('email',)
    ordering = ('email',)
    fieldsets = (
        (None, {'fields': ('email', 'password', 'balance')}),  # Added 'balance' here
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'trade_group', 'user_permissions', 'open_trades', 'transactions', 'token', 'is_verified')}),
        ('Important dates', {'fields': ('date_joined',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'balance', 'is_active', 'is_staff')}
        ),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.set_password(form.cleaned_data['password1'])  # Use set_password to hash the password
        obj.save()


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'is_processed', 'request_date')
    list_filter = ('is_processed', 'request_date')
    actions = ['mark_as_withdrawn']

    def mark_as_withdrawn(self, request, queryset):
        queryset.update(is_processed=True)
        for withdrawal in queryset:
            # Log the transaction as "withdrawal" once processed
            Transaction.objects.create(user=withdrawal.user, transaction_type='withdrawal', amount=withdrawal.amount)
        self.message_user(request, "Selected withdrawal requests marked as processed.")
    mark_as_withdrawn.short_description = "Mark selected requests as Withdrawn"


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'transaction_type', 'amount', 'date')
    list_filter = ('transaction_type', 'date')


@admin.register(KYC)
class KYCAdmin(admin.ModelAdmin):
    list_display = ('user', 'status', 'submitted_at')
    actions = ['approve_kyc', 'reject_kyc']

    def approve_kyc(self, request, queryset):
        queryset.update(status='approved')
        for kyc in queryset:
            kyc.user.kyc_status = 'approved'
            kyc.user.save()

    def reject_kyc(self, request, queryset):
        queryset.update(status='rejected')
        for kyc in queryset:
            kyc.user.kyc_status = 'rejected'
            kyc.user.save()

    approve_kyc.short_description = "Approve selected KYC applications"
    reject_kyc.short_description = "Reject selected KYC applications"

# Register the custom user model with the admin site
admin.site.register(CustomUser, CustomerUserAdmin)
admin.site.register(DepositOption)
admin.site.register(DepositRequest)
admin.site.register(Trade)
admin.site.register(CrptoId)
admin.site.register(TradeGroup)

