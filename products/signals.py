from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from core.context_processors import NAV_CATEGORIES_CACHE_KEY

from .models import Category, Product, ProductVariant, Review
from .services import notify_back_in_stock


@receiver([post_save, post_delete], sender=Category)
def invalidate_category_cache(sender, **kwargs):
    cache.delete(NAV_CATEGORIES_CACHE_KEY)


@receiver([post_save, post_delete], sender=Review)
def refresh_product_rating(sender, instance, raw=False, **kwargs):
    if raw:
        return
    product = Product.objects.filter(pk=instance.product_id).first()
    if product is not None:
        product.update_rating()


def _schedule_stock_notification(product_id):
    transaction.on_commit(lambda: notify_back_in_stock(product_id))


@receiver(post_save, sender=Product)
def product_stock_changed(sender, instance, raw=False, **kwargs):
    """Stock can change via vendor forms, the inventory page or the admin."""
    if not raw and instance.stock > 0 and instance.stock_alerts.filter(notified_at__isnull=True).exists():
        _schedule_stock_notification(instance.pk)


@receiver(post_save, sender=ProductVariant)
def variant_stock_changed(sender, instance, raw=False, **kwargs):
    if raw or not instance.is_active or instance.stock <= 0:
        return
    if instance.product.stock_alerts.filter(notified_at__isnull=True).exists():
        _schedule_stock_notification(instance.product_id)
