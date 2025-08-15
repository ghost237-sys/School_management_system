from django import forms
from .models import SiteSettings, GalleryImage, Category, CategoryMedia

class SiteSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = [
            "school_name", "school_aim", "school_motto",
            "primary_color", "secondary_color", "logo", "favicon", "logo_url", "favicon_url",
            "hero_title", "hero_subtitle", "hero_background_url", "hero_video", "hero_video_url", "hero_cta_text", "hero_cta_link",
            "about_title", "about_text",
            "contact_email", "contact_phone", "contact_address", "footer_text",
            "facebook_url", "twitter_url", "instagram_url",
        ]
        widgets = {
            "school_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "School Name"}),
            "school_aim": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "School Aim"}),
            "school_motto": forms.TextInput(attrs={"class": "form-control", "placeholder": "School Motto"}),
            "primary_color": forms.TextInput(attrs={"class": "form-control", "type": "color"}),
            "secondary_color": forms.TextInput(attrs={"class": "form-control", "type": "color"}),
            "logo": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "favicon": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "logo_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://..."}),
            "favicon_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://..."}),
            "hero_title": forms.TextInput(attrs={"class": "form-control", "placeholder": "Hero Title"}),
            "hero_subtitle": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Hero Subtitle"}),
            "hero_background_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "Background image URL"}),
            "hero_video": forms.ClearableFileInput(attrs={"class": "form-control", "accept": "video/*"}),
            "hero_video_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://... (MP4 recommended)"}),
            "hero_cta_text": forms.TextInput(attrs={"class": "form-control", "placeholder": "CTA Text"}),
            "hero_cta_link": forms.TextInput(attrs={"class": "form-control", "placeholder": "/login/"}),
            "about_title": forms.TextInput(attrs={"class": "form-control", "placeholder": "About Title"}),
            "about_text": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "About section text"}),
            "contact_email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "info@school.com"}),
            "contact_phone": forms.TextInput(attrs={"class": "form-control", "placeholder": "+254 7xx xxx xxx"}),
            "contact_address": forms.TextInput(attrs={"class": "form-control", "placeholder": "Street, City"}),
            "footer_text": forms.TextInput(attrs={"class": "form-control", "placeholder": "© 2025 Greenwood High"}),
            "facebook_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://facebook.com/..."}),
            "twitter_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://x.com/..."}),
            "instagram_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://instagram.com/..."}),
        }


class CategoryMediaForm(forms.ModelForm):
    class Meta:
        model = CategoryMedia
        fields = ["category", "kind", "image", "file", "video_url", "caption", "order"]
        widgets = {
            "category": forms.Select(attrs={"class": "form-select"}),
            "kind": forms.Select(attrs={"class": "form-select"}),
            "image": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "file": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "video_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://youtu.be/..."}),
            "caption": forms.TextInput(attrs={"class": "form-control", "placeholder": "Optional caption"}),
            "order": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
        }


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "description", "video_side_text", "template", "order", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Admissions"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Short description to show on homepage"}),
            "video_side_text": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Optional side text shown next to the video."}),
            "template": forms.Select(attrs={"class": "form-select"}),
            "order": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

class GalleryImageForm(forms.ModelForm):
    class Meta:
        model = GalleryImage
        fields = ["title", "caption", "image", "is_featured"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "Title (optional)"}),
            "caption": forms.TextInput(attrs={"class": "form-control", "placeholder": "Caption (optional)"}),
            "image": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }
