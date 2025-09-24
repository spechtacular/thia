"""
This file contains forms for the AppUser model.
It includes forms for creating and changing user profiles, as well as a public signup form.
"""
from django import forms
from django.utils import timezone
from django.contrib.auth.forms import (UserCreationForm,
                                       UserChangeForm,
                                        PasswordChangeForm,
                                        PasswordResetForm,
                                        SetPasswordForm)
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

class EventVolunteerFilterForm(forms.Form):
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control form-control-sm"})
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control form-control-sm"})
    )
    future_only = forms.BooleanField(
        required=False,
        label="Future only",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )


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
    class Meta:
        model = EventVolunteers
        fields = ["confirmed", "signed_in", "makeup", "costume"]
        widgets = {
            "confirmed": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "signed_in": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "makeup": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "costume": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

class UserPrepForm(forms.ModelForm):
    class Meta:
        model = AppUser
        fields = [
            "costume_size",
            "safety_class",
            "waiver",
            "room_actor_training",
            "line_actor_training",
            "wear_mask",
        ]
        widgets = {
            # If costume_size has choices in your model, Django will render a <select> automatically.
            # Otherwise, you can force a select or leave TextInput:
            # "costume_size": forms.Select(attrs={"class": "form-select"}),
             "costume_size": forms.Select(
                attrs={
                    "class": "form-select form-select-sm w-auto",
                    # fixed/limited width so it doesn't push checkboxes to the next line
                    "style": "max-width: 220px; min-width: 160px;",
                }
            ),
            "safety_class": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "waiver": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "room_actor_training": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "line_actor_training": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "wear_mask": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        f = self.fields["costume_size"]
        inst = self.instance if hasattr(self, "instance") else None
        current = getattr(inst, "costume_size", None) if inst is not None else None

        # Only massage defaults on GET (unbound) and when the user has no value
        if not self.is_bound and (current is None or current == ""):
            default = AppUser._meta.get_field("costume_size").default
            if default not in (None, ""):
                default = str(default)

                # 1) Make field required so Django doesn't inject an empty "<option>"
                f.required = True

                # 2) Reorder choices to put the default first (but keep labels/others intact)
                choices = list(f.choices)

                # If there is an empty option, drop it because we're forcing a default
                choices = [c for c in choices if str(c[0]) not in ("", "None")]

                # Put default at the front if it exists in the value set
                if any(str(v) == default for v, _ in choices):
                    choices = (
                        [next(c for c in choices if str(c[0]) == default)] +
                        [c for c in choices if str(c[0]) != default]
                    )
                f.choices = choices

                # 3) Set initial so the widget renders selected=default
                self.initial["costume_size"] = default
                f.initial = default




class StyledPasswordResetForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.update({"class": "form-control"})

class StyledSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("new_password1", "new_password2"):
            self.fields[name].widget.attrs.update({"class": "form-control"})

class StyledPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Django’s PasswordChangeForm uses old_password, new_password1, new_password2
        self.fields["old_password"].widget.attrs.update({"class": "form-control"})
        self.fields["new_password1"].widget.attrs.update({"class": "form-control"})
        self.fields["new_password2"].widget.attrs.update({"class": "form-control"})

