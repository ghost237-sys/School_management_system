"""
URL configuration for Analitica project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from core import views as core_views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Include core URLs first so any custom admin-like routes defined there
    # (e.g., 'admin/fees/mpesa/reconcile/') are matched BEFORE Django admin's catch-all
    path('', include('core.urls')),
    # Include with explicit namespace so {% url 'assistant:...' %} resolves
    path('assistant/', include(('assistant.urls', 'assistant'), namespace='assistant')),
    # Direct mapping to ensure availability even if includes are stale
    path('timetable/auto-generate/', core_views.timetable_auto_generate, name='timetable_auto_generate'),
    path('admin/', admin.site.urls),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # DEBUG-only catch-all route to preview custom 404 for any invalid path
    # This must be LAST so it doesn't shadow valid routes
    urlpatterns += [
        re_path(r'^(?P<unused_path>.*)$', core_views.custom_404_catchall),
    ]

# Custom error handlers (used when DEBUG=False)
handler404 = 'core.views.custom_404'
handler403 = 'core.views.custom_403'
