from django import forms
from django.contrib import admin
from django.utils.html import format_html
from .models import Organization, OrganizationMember, OrganizationInvite


class OrganizationForm(forms.ModelForm):
    """Custom form to ensure files go to S3"""
    class Meta:
        model = Organization
        fields = '__all__'
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        # Force S3 storage for logo
        if self.cleaned_data.get('logo'):
            from storages.backends.s3boto3 import S3Boto3Storage
            storage = S3Boto3Storage()
            # The file is already being saved by Django's form
            pass
        if commit:
            instance.save()
        return instance


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    form = OrganizationForm
    list_display = ('name', 'slug', 'industry', 'logo_preview', 'created_at')
    readonly_fields = ('logo_preview', 'created_at')
    search_fields = ('name', 'slug')
    list_filter = ('industry', 'created_at')
    prepopulated_fields = {'slug': ('name',)}
    
    def logo_preview(self, obj):
        """Display logo preview"""
        if obj.logo:
            url = obj.get_logo_url()
            return format_html(
                f'<a href="{url}" target="_blank">'
                f'<img src="{url}" width="150" style="border-radius: 5px;" />'
                f'</a>'
            )
        return "No logo"
    
    logo_preview.short_description = "Logo Preview"


@admin.register(OrganizationMember)
class OrganizationMemberAdmin(admin.ModelAdmin):
    list_display = ('user', 'organization', 'role', 'joined_at')
    list_filter = ('role', 'joined_at', 'organization')
    search_fields = ('user__email', 'organization__name')
    readonly_fields = ('joined_at',)


@admin.register(OrganizationInvite)
class OrganizationInviteAdmin(admin.ModelAdmin):
    list_display = ('email', 'organization', 'role', 'is_accepted', 'expires_at')
    list_filter = ('role', 'is_accepted', 'created_at', 'expires_at')
    search_fields = ('email', 'organization__name')
    readonly_fields = ('token', 'id', 'created_at')