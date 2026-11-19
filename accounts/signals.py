from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import CustomerProfile, CustomUser, Wishlist


@receiver(post_save, sender=CustomUser)
def ensure_user_related_records(sender, instance, created, raw=False, **kwargs):
    """
    Every user gets a wishlist; customers get a profile. Vendor profiles are created
    by vendor registration because they require business details.
    """
    if raw:
        return
    if created:
        Wishlist.objects.get_or_create(user=instance)
    if instance.is_customer:
        CustomerProfile.objects.get_or_create(user=instance)
