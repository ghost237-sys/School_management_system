from django.contrib import admin
from .models import SiteSettings

@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ("school_name", "restrict_results_by_fee", "fee_restriction_threshold", "updated_at")
    search_fields = ("school_name",)
    fieldsets = (
        (None, {
            'fields': ("school_name", "school_aim", "school_motto")
        }),
        ("Look & Feel", {
            'fields': ("primary_color", "secondary_color", "logo", "favicon", "logo_url", "favicon_url"),
            'classes': ("collapse",)
        }),
        ("Hero", {
            'fields': ("hero_title", "hero_subtitle", "hero_background_url", "hero_video", "hero_video_url", "hero_cta_text", "hero_cta_link"),
            'classes': ("collapse",)
        }),
        ("About", {
            'fields': ("about_title", "about_text"),
            'classes': ("collapse",)
        }),
        ("Contact & Footer", {
            'fields': ("contact_email", "contact_phone", "contact_address", "facebook_url", "twitter_url", "instagram_url", "footer_text"),
            'classes': ("collapse",)
        }),
        ("Results Access Restriction", {
            'fields': ("restrict_results_by_fee", "fee_restriction_threshold", "fee_restriction_message"),
        }),
        ("System", {
            'fields': ("updated_at",),
            'classes': ("collapse",),
        }),
    )
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        # Enforce singleton: only one SiteSettings instance
        if SiteSettings.objects.exists():
            return False
        return super().has_add_permission(request)
