"""
This file contains forms for the AppUser model.
It includes forms for creating and changing user profiles, as well as a public signup form.
"""
from django import forms
from django.utils import timezone
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import AppUser, EventVolunteers

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
                   'city', 'state', 'phone1', 'phone2', 'ice_name', 'ice_phone', 'company',
                   'country',
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
                   'city', 'state', 'phone1', 'phone2', 'ice_name', 'ice_phone', 'company',
                   'country',
                   'ice_relationship', 'wear_mask', 'referral_source', 'haunt_experience',
                   'allergies', 'zipcode', 'first_name', 'last_name', 'waiver')
        widgets = {
            'date_of_birth': forms.SelectDateWidget(years=range(1900, timezone.now().year+1)),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for fld in self.fields.values():
            fld.widget.attrs.update({'class': 'form-control'})

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for fld in self.fields.values():
            # Password fields already render as <input type="password">
            fld.widget.attrs.update({'class': 'form-control'})

class ProfileForm(UserChangeForm):
    """
    user profile page , updates to the user info is made here
    """
    class Meta:
        model = AppUser
        # list exactly the fields you *do* want—do NOT include "password"
        fields = (
            'email', 'first_name', 'last_name',
            'image_url', 'date_of_birth', 'image_url',
            'phone1', 'phone2', 'ice_relationship', 'ice_name', 'ice_phone',
            'tshirt_size', 'address', 'city', 'city', 'state', 'point_total'
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Just in case, remove the password field if it sneaks in
        self.fields.pop('password', None)


class EventPrepForm(forms.ModelForm):
    """
    Exposes the Boolean prep flags on EventVolunteers as checkboxes.
    """
    class Meta:
        model = EventVolunteers
        fields = [
            'confirmed', 'signed_in', 'makeup', 'costume',
            'waiver', 'wear_mask', 'waitlist', 'conflict',
        ]
        widgets = {
            name: forms.CheckboxInput(attrs={'class': 'form-check-input'})
            for name in fields
        }
        labels = {
            'confirmed': 'Confirmed',
            'signed_in': 'Signed In',
            'makeup': 'Makeup',
            'costume': 'Costume',
            'wear_mask': 'Wear Mask',
            'waiver': 'Waiver Signed',
            'waitlist': 'Waitlist',
            'conflict': 'Conflict',
        }
