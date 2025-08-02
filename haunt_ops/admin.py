"""
This file contains the admin configuration for the AppUser model.
It customizes the admin interface for managing user profiles.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin 
from .forms import AppUserCreationForm, AppUserChangeForm
# Register your models here.
from .models import AppUser


class AppUserAdmin(UserAdmin):
    """    
    Custom admin interface for AppUser model.
    Uses AppUserCreationForm for adding new users and AppUserChangeForm for changing existing users.
    """
    add_form = AppUserCreationForm
    form = AppUserChangeForm
    model = AppUser
    list_display = ["email", "is_staff", "is_superuser"]
    list_filter = ("is_staff", "is_superuser", "is_active", "phone1", "ice_phone","date_of_birth")
    search_fields = ["email", "first_name", "last_name"]
    ordering = ["email"]
    list_display_links = ["email"]

    fieldsets = (
        (None, {'fields':  ('email', )}),
        ('Personal Info', {
                  'fields': ('first_name','last_name','image_url', 'date_of_birth', 'address', 'tshirt_size', 'city', 
                     'state', 'phone1', 'phone2', 'ice_name', 'ice_phone', 'ice_relationship', 'wear_mask',
                     'referral_source', 'haunt_experience', 'allergies', 'zipcode','country','company')
        }),
        ('Permissions', {
                  'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Important dates', {
                   'fields': ( 'last_login', 'last_activity', 'date_joined')
        })
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': (
                'email', 'password1', 'password2',
                'first_name', 'last_name', 'image_url', 'date_of_birth', 'address', 'tshirt_size',
                'city', 'state', 'zipcode', 'country', 'company', 'phone1', 'phone2',
                'ice_name', 'ice_relationship', 'ice_phone', 'wear_mask',
                'referral_source', 'haunt_experience', 'allergies',
                'is_active', 'is_staff', 'is_superuser')
         }),

    )

admin.site.register(AppUser, AppUserAdmin)

