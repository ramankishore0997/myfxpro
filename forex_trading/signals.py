from django.db.models.signals import post_save, post_delete, m2m_changed, pre_delete
from django.dispatch import receiver
from .models import Trade, CustomUser
from django.conf import settings
from django.db.models import F


@receiver(m2m_changed, sender=Trade.trade_group.through)
def update_user_balance(sender, instance, action, **kwargs):
    """
    Signal to update user balance when trade_group relationships change.
    """
    if action == 'post_add':  # Trigger only after groups are added
        groups = instance.trade_group.all()
        if groups.exists():
            print("Groups associated:", groups)
            # Update all users in the associated groups
            CustomUser.objects.filter(trade_group__in=groups).update(balance=F('balance') + instance.profit)
        else:
            print("No groups found for this trade.")


# Cache the trade groups before deletion
@receiver(pre_delete, sender=Trade)
def cache_trade_groups(sender, instance, **kwargs):
    instance.cached_groups = list(instance.trade_group.all())

# Adjust balances after deletion
@receiver(post_delete, sender=Trade)
def update_user_balance_on_trade_delete(sender, instance, **kwargs):
    try:
        # Use the cached groups
        groups = instance.cached_groups
        print("Groups ", groups)
    except AttributeError:
        print("Trade groups were not cached. Skipping balance adjustment.")
        return

    if groups:
        # Adjust the balance for all users in the groups
        if instance.profit > 0:
            # Subtract profit for profitable trades
            CustomUser.objects.filter(trade_group__in=groups).update(balance=F('balance') - instance.profit)
        else:
            # Add the loss back to the balance for losing trades
            CustomUser.objects.filter(trade_group__in=groups).update(balance=F('balance') + abs(instance.profit))
    else:
        print("No groups found for this trade.")