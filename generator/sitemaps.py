from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import SavedConfig, StackTemplate, UserStack


class StaticSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 1.0
    protocol = 'https'

    def items(self):
        return ['index', 'builder', 'community']

    def location(self, item):
        return reverse(item)


class SavedConfigSitemap(Sitemap):
    changefreq = 'never'
    priority = 0.4
    protocol = 'https'

    def items(self):
        return SavedConfig.objects.all()

    def location(self, obj):
        return reverse('saved_detail', kwargs={'uuid': obj.uuid})

    def lastmod(self, obj):
        return obj.created_at


class StackSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.9
    protocol = 'https'

    def items(self):
        return StackTemplate.objects.filter(is_active=True).order_by('key')

    def location(self, obj):
        return reverse('stack_detail', kwargs={'key': obj.key})

    def lastmod(self, obj):
        return obj.created_at


class CommunityStackSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.6
    protocol = 'https'

    def items(self):
        return UserStack.objects.filter(is_approved=True).order_by('-created_at')

    def location(self, obj):
        return reverse('community_stack_detail', kwargs={'stack_id': obj.pk})

    def lastmod(self, obj):
        return obj.created_at
