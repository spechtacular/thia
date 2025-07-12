from django import forms
from django.utils import timezone
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import AppUser

class AppUserCreationForm(UserCreationForm):
    class Meta:
        model = AppUser
        fields = ( 'email', 'username', 'image_url', 'date_of_birth', 'address', 'tshirt_size', 
                   'city', 'state', 'phone1', 'phone2', 'ice_name', 'ice_phone', 'company','country',
                   'ice_relationship', 'wear_mask', 'referral_source', 'haunt_experience', 
                   'allergies', 'zipcode', 'first_name', 'last_name', 'waiver')

class AppUserChangeForm(UserChangeForm):
    class Meta:
        model = AppUser
        fields = ( 'email', 'username', 'image_url', 'date_of_birth', 'address', 'tshirt_size', 
                   'city', 'state', 'phone1', 'phone2', 'ice_name', 'ice_phone', 'company','country',
                   'ice_relationship', 'wear_mask', 'referral_source', 'haunt_experience', 
                   'allergies', 'zipcode', 'first_name', 'last_name', 'waiver') 
        widgets = {
            'date_of_birth': forms.SelectDateWidget(years=range(1900, timezone.now().year+1)),
        }

class PublicSignupForm(UserCreationForm):
    class Meta:
        model = AppUser
        fields = ('username', 'email', 'password1', 'password2')
