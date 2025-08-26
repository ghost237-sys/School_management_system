from django.db import models
from django.utils.text import slugify

class SiteSettings(models.Model):
    """Singleton-style settings for the public website."""
    school_name = models.CharField(max_length=255, default="Greenwood High")
    school_aim = models.TextField(blank=True, default="To nurture and inspire every student to reach their full potential.")
    school_motto = models.CharField(max_length=255, blank=True, default="Excellence Through Diligence")
    # Look & Feel
    primary_color = models.CharField(max_length=20, blank=True, default="#0d6efd")
    secondary_color = models.CharField(max_length=20, blank=True, default="#6c757d")
    # Prefer uploaded files; keep URL fields for fallback
    logo = models.ImageField(upload_to='branding/', blank=True, null=True)
    favicon = models.ImageField(upload_to='branding/', blank=True, null=True)
    logo_url = models.URLField(blank=True, default="")
    favicon_url = models.URLField(blank=True, default="")
    # Hero section
    hero_title = models.CharField(max_length=255, blank=True, default="Welcome to Our School")
    hero_subtitle = models.CharField(max_length=512, blank=True, default="Empowering students to excel in academics and life.")
    hero_background_url = models.URLField(blank=True, default="")
    # Optional background video for landing hero
    hero_video = models.FileField(upload_to='branding/', blank=True, null=True)
    hero_video_url = models.URLField(blank=True, default="")
    hero_cta_text = models.CharField(max_length=100, blank=True, default="Login to Portal")
    hero_cta_link = models.CharField(max_length=255, blank=True, default="/login/")
    # About section
    about_title = models.CharField(max_length=255, blank=True, default="About Us")
    about_text = models.TextField(blank=True, default="We are committed to providing a holistic education that nurtures character and academic excellence.")
    # Contact/Footer
    contact_email = models.EmailField(blank=True, default="")
    contact_phone = models.CharField(max_length=50, blank=True, default="")
    contact_address = models.CharField(max_length=255, blank=True, default="")
    footer_text = models.CharField(max_length=255, blank=True, default="© {{year}} All rights reserved.")
    facebook_url = models.URLField(blank=True, default="")
    twitter_url = models.URLField(blank=True, default="")
    instagram_url = models.URLField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)
    # Results access restrictions
    restrict_results_by_fee = models.BooleanField(
        default=False,
        help_text="If enabled, students with fee balances above the threshold cannot view or download results."
    )
    fee_restriction_threshold = models.PositiveIntegerField(
        default=50,
        help_text="Block results if balance percent is greater than this value (e.g., 50 = balance > 50%)."
    )
    fee_restriction_message = models.CharField(
        max_length=255,
        blank=True,
        default="Results are temporarily unavailable due to outstanding fees. Please clear at least 50% to access.",
        help_text="Message shown to restricted students."
    )

    class Meta:
        verbose_name = "Site Settings"
        verbose_name_plural = "Site Settings"

    def __str__(self):
        return self.school_name


class GalleryImage(models.Model):
    """Gallery images for the public website."""
    title = models.CharField(max_length=255, blank=True, default="")
    caption = models.CharField(max_length=512, blank=True, default="")
    image = models.ImageField(upload_to='gallery/', blank=False, null=False)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Gallery Image"
        verbose_name_plural = "Gallery Images"

    def __str__(self):
        return self.title or f"Image #{self.pk}"


class Category(models.Model):
    """Simple nav categories managed by admin and shown in the public navbar."""
    name = models.CharField(max_length=100)
    link_url = models.CharField(max_length=255, help_text="URL or path, e.g. /admissions/ or https://...")
    description = models.TextField(blank=True, default="")
    TEMPLATE_CHOICES = [
        ("card", "Card Grid"),
        ("feature", "Feature Block"),
        ("highlight", "Highlight Banner"),
        ("single_photo", "Single Photo"),
        ("gallery", "Photo Gallery"),
        ("video", "Video"),
        ("file", "Download File"),
        ("all_media", "All Media")
    ]
    template = models.CharField(max_length=20, choices=TEMPLATE_CHOICES, default="card")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Optional side text for the Video template
    video_side_text = models.TextField(blank=True, default="")

    class Meta:
        ordering = ['order', 'name']
        verbose_name = "Category"
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name

    def template_path(self):
        return f"landing/category_templates/{self.template}.html"

    def save(self, *args, **kwargs):
        # Auto-generate in-page anchor link from name
        try:
            anchor = slugify(self.name or "")
            if anchor:
                self.link_url = f"#{anchor}"
        except Exception:
            pass
        super().save(*args, **kwargs)


class CategoryMedia(models.Model):
    KIND_CHOICES = [
        ("image", "Image"),
        ("video", "Video"),
        ("file", "File"),
    ]
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="media")
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    image = models.ImageField(upload_to='category_media/images/', max_length=255, blank=True, null=True)
    file = models.FileField(upload_to='category_media/files/', max_length=255, blank=True, null=True)
    video_url = models.URLField(blank=True, default="", help_text="YouTube/Vimeo URL or direct video URL")
    caption = models.CharField(max_length=255, blank=True, default="")
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', '-created_at']
        verbose_name = "Category Media"
        verbose_name_plural = "Category Media"

    def __str__(self):
        return f"{self.kind} for {self.category.name}"

