import threading
import urllib.request
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import StackTemplate, UserStack, SavedConfig, UserProfile
from .mail import send_app_mail, mail_account_activated


def _ping_search_engines(page_url: str):
    sitemap_url = f"{settings.SITE_URL}/sitemap.xml"
    endpoints = [
        f"https://www.bing.com/ping?sitemap={sitemap_url}",
        f"https://www.bing.com/indexnow?url={page_url}&key=podman-kube-gen",
    ]
    for url in endpoints:
        try:
            urllib.request.urlopen(url, timeout=5)
        except Exception:
            pass


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def user_activated(sender, instance, created, **kwargs):
    """E-Mail senden wenn ein Account auf is_active=True gesetzt wird."""
    if created:
        return
    if not instance.is_active or not instance.email:
        return
    update_fields = kwargs.get('update_fields')
    if update_fields is not None and 'is_active' not in update_fields:
        return
    site_url = getattr(settings, 'SITE_URL', '')
    subject, html = mail_account_activated(instance.username, site_url)
    send_app_mail(subject=subject, body=html, recipient_list=[instance.email])


@receiver(post_save, sender=StackTemplate)
def stack_saved(sender, instance, **kwargs):
    if not instance.is_active:
        return
    page_url = f"{settings.SITE_URL}/stack/{instance.key}/"
    threading.Thread(target=_ping_search_engines, args=(page_url,), daemon=True).start()


@receiver(post_save, sender=SavedConfig)
def saved_config_created(sender, instance, created, **kwargs):
    if not created:
        return
    page_url = f"{settings.SITE_URL}/{instance.uuid}/"
    threading.Thread(target=_ping_search_engines, args=(page_url,), daemon=True).start()


@receiver(post_save, sender=UserStack)
def community_stack_approved(sender, instance, **kwargs):
    if not instance.is_approved:
        return
    page_url = f"{settings.SITE_URL}/community/{instance.pk}/"
    threading.Thread(target=_ping_search_engines, args=(page_url,), daemon=True).start()
