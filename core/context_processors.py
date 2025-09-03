from landing.models import SiteSettings

def site_settings(request):
    return {
        'site_settings': SiteSettings.objects.order_by('-updated_at').first()
    }
