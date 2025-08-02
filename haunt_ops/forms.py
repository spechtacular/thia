"""
This file contains forms for the AppUser model.
It includes forms for creating and changing user profiles, as well as a public signup form.
"""
from django import forms
from django.utils import timezone
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import AppUser

class AppUserCreationForm(UserCreationForm):
    """
    Form for creating a new AppUser.
    It includes fields for email, username, and personal information.
    """
    class Meta:
        """
        Meta class for AppUserCreationForm.
        It specifies the model and fields to be included in the form.
        """
        model = AppUser
        fields = ( 'email', 'username', 'image_url', 'date_of_birth', 'address', 'tshirt_size', 
                   'city', 'state', 'phone1', 'phone2', 'ice_name', 'ice_phone', 'company','country',
                   'ice_relationship', 'wear_mask', 'referral_source', 'haunt_experience', 
                   'allergies', 'zipcode', 'first_name', 'last_name', 'waiver')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure the password field is not present
        self.fields.pop('password', None)


class AppUserChangeForm(UserChangeForm):
    """
    Form for changing an existing AppUser.
    It includes fields for email, username, and personal information.
    """
    class Meta:
        """
        Meta class for AppUserChangeForm.
        It specifies the model and fields to be included in the form.
        """
        model = AppUser
        fields = ( 'email', 'username', 'image_url', 'date_of_birth', 'address', 'tshirt_size', 
                   'city', 'state', 'phone1', 'phone2', 'ice_name', 'ice_phone', 'company','country',
                   'ice_relationship', 'wear_mask', 'referral_source', 'haunt_experience', 
                   'allergies', 'zipcode', 'first_name', 'last_name', 'waiver') 
        widgets = {
            'date_of_birth': forms.SelectDateWidget(years=range(1900, timezone.now().year+1)),
        }

class PublicSignupForm(UserCreationForm):
    """
    Public signup form for creating a new AppUser.
    It includes fields for email, username, and personal information.
    """
    class Meta:
        """
        Meta class for PublicSignupForm.
        It specifies the model and fields to be included in the form.
        """
        
        model = AppUser
        fields = ( 'email', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        if not user.username:
            # rely on manager normally, but ensure here too
            user.username = user.email
        if commit:
            user.save()
        return user
