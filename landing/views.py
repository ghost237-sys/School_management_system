from django.shortcuts import render
from .models import SiteSettings, GalleryImage, Category

def landing_page(request):
    # Fetch singleton settings (or use defaults if none exist yet)
    settings = SiteSettings.objects.order_by('-updated_at').first()
    context = {
        'school_name': getattr(settings, 'school_name', 'Greenwood High'),
        'school_aim': getattr(settings, 'school_aim', 'To nurture and inspire every student to reach their full potential.'),
        'school_motto': getattr(settings, 'school_motto', 'Excellence Through Diligence'),
        'settings': settings,
        'gallery_images': GalleryImage.objects.all()[:12],
        'categories': Category.objects.filter(is_active=True).order_by('order', 'name'),
    }
    return render(request, 'landing/index.html', context)


# Create your views here.
