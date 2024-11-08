from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Trade
from django.conf import settings


@receiver(post_save, sender=Trade)
def update_user_balance(sender, instance, created, **kwargs):
    if created:
        # Trade has been added, update the user's balance
        user = instance.user
        print(instance, user)
        # Add or subtract the profit to/from the balance
        user.balance += instance.profit  # For positive profit, it adds. For negative profit, it subtracts.
        user.save()


@receiver(post_delete, sender=Trade)
def update_user_balance_on_trade_delete(sender, instance, **kwargs):
    user = instance.user
    # Update user balance based on the profit or loss from the deleted trade
    if instance.profit > 0:
        user.balance -= instance.profit  # Subtract profit if the trade was profitable
    else:
        user.balance += abs(instance.profit)  # Add to balance if the trade was a loss

    user.save()  # Save the updated balance