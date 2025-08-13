"""
This file contains the models for the HauntOps application.
It includes the AppUser model, Groups model, and related models
  for managing user profiles and groups.
"""
from django.utils import timezone
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.base_user import BaseUserManager
from django.utils.translation import gettext_lazy as _
from django.db.models import UniqueConstraint
from django.db.models.functions import Lower
# we have a custom user table so lets get the table name from the settings file
from django.conf import settings

from django.db import models


class AppUserManager(BaseUserManager):
    """
        Manager for AppUser model.
        It provides methods to create users and superusers with email as the unique identifier.
    """
    def create_user(self, email, password=None, **extra_fields):
        """
        Create and return a user with an email and password.
        Extra fields can be provided for additional user attributes.
        """
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        extra_fields.setdefault('username',email)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create and return a superuser with an email and password.
        Extra fields can be provided for additional user attributes.
        """
        extra_fields.setdefault("username", email)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        return self.create_user(email=email, password=password, **extra_fields)


class AppUser(AbstractUser):
    """
    Custom user model for the HauntOps application.
    It extends the AbstractUser model and includes additional fields specific to the application.
    """
    first_name = models.CharField(max_length=30, blank=False, null=False)
    last_name = models.CharField(max_length=30, blank=False, null=False)
    email = models.CharField(max_length=150, unique=True)
    username = models.CharField(max_length=150, unique=True)
    image_url = models.CharField(max_length=200, blank=True, default="default.jpg")
    tshirt_size = models.CharField(max_length=12, default="unknown")
    address = models.CharField(max_length=100, default="unknown")
    city = models.CharField(max_length=100, blank=True, default="unknown")
    state = models.CharField(max_length=30, default="CA")
    zipcode = models.CharField(max_length=20, default="unknown")
    country = models.CharField(max_length=30, default="USA")
    company = models.CharField(max_length=100, blank=True, default="unknown")
    phone1 = models.CharField(max_length=12, null=False, blank=False, default="unknown")
    phone2 = models.CharField(max_length=12, blank=True, null=True)
    date_of_birth = models.DateField(null=False,blank=False, default=timezone.now)
    last_activity = models.DateTimeField(null=False, default=timezone.now)
    email_blocked = models.BooleanField(default=False)
    ice_name = models.CharField(max_length=100, null=False, blank=False)
    ice_relationship = models.CharField(max_length=100, null=False, blank=False)
    ice_phone = models.CharField(max_length=12, null=False, blank=False)
    wear_mask = models.BooleanField(default=False)
    referral_source =  models.CharField(max_length=500,  null=True, blank=True)
    haunt_experience =  models.CharField(max_length=500,  null=True, blank=True, default="none")
    allergies =  models.CharField(max_length=100, null=True, blank=True, default="none")
    waiver = models.BooleanField(default=False)
    point_total = models.FloatField(null=False,blank=False,default=0.0)



    USERNAME_FIELD = 'email'
    # required fields is only used when running createsuperuser
    REQUIRED_FIELDS = []

    objects = AppUserManager()

    class Meta:
        """
        Meta class for AppUser"
        """
        db_table = 'app_user'
        ordering = ['last_name']

    def __str__(self):
        return self.email



    def save(self, *args, **kwargs):
        """
            Override Save method for AppUser model.
            It ensures that the username is set to the email if not provided.
            This is a fix to the signup issue I had:
            You're setting extra_fields.setdefault("username", email) in the manager,
            but your signup path (via UserCreationForm) is not using the manager—
            it creates the model instance and calls user.save() directly.
            So your manager logic never runs, and username stays empty.
        """
        if not self.username and self.email:
            self.username = self.email
        super().save(*args, **kwargs)

class Groups(models.Model) :
    """
    Model representing groups in the HauntOps application.
    It includes fields for group name and points associated with the group.
    """
    id = models.BigAutoField(primary_key=True)
    #group_name = models.CharField(max_length=100, unique=True, null=False, blank=False)
    group_name = models.CharField(max_length=100, unique=True, null=True, blank=True)

    group_points = models.IntegerField(default=1)

    class Meta:
        """
            Meta class for Groups.
            It specifies the database table name for the model.
        """
        db_table = 'groups'
        ordering = ['group_name']
        constraints = [
            UniqueConstraint(Lower('group_name'), name='uniq_group_name_ci')
        ]

    def __str__(self)->str:
        return self.group_name or "Unnamed Group"

class Events(models.Model) :
    """
    Model representing events in the HauntOps application.
    It includes fields for event date, name, and status.
    """
    id = models.BigAutoField(primary_key=True)
    event_date = models.DateField(blank=False,null=False)
    event_name = models.CharField(max_length=500, blank=False,null=False)
    event_status = models.TextField(max_length=50, default="TBD")
    class Meta:
        """
        Meta class for Events.
        It specifies the database table name for the model.
        This model is not managed by Django migrations,
            meaning it is expected to be created and managed by the database directly.
        This is useful for legacy tables or when the
            table structure is controlled outside of Django.
        """
        db_table = 'events'
        ordering = ['event_date']

    def __str__(self):
        return f"{self.event_name or 'Unnamed Event'} "

class GroupVolunteers(models.Model):
    """
    Model correlating Haunt Users with groups they have participated in.
    """
    id = models.BigAutoField(primary_key=True)

    volunteer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='group_volunteers_as_volunteer'
    )

    group = models.ForeignKey(
        Groups,
        on_delete=models.CASCADE,
        related_name='group_volunteers'
    )

    class Meta:
        db_table = 'group_volunteers'
        ordering = ['group']


class EventVolunteers(models.Model):
    """
    Model representing volunteers for events in the HauntOps application.
    It includes fields for start and end time, volunteer details, task, and event association.
    """
    id = models.BigAutoField(primary_key=True)
    start_time = models.DateTimeField(blank=True)
    end_time = models.DateTimeField(blank=True)
    volunteer = models.ForeignKey(AppUser, models.DO_NOTHING)
    event = models.ForeignKey(Events, models.DO_NOTHING)
    task = models.TextField(blank=True, null=True)
    slot_column = models.TextField(blank=True)
    slot_row = models.TextField(blank=True)
    signed_in = models.BooleanField(blank=True,  default=False)
    conflict = models.BooleanField(blank=True,  default=False)
    confirmed = models.BooleanField(blank=True,  default=False)
    waitlist = models.BooleanField(blank=True,  default=False)
    points = models.FloatField(blank=True,  default=0.0)
    event_name = models.TextField(blank=True, null=True)
    under_18 = models.BooleanField(blank=True,  default=False)
    under_16 = models.BooleanField(blank=True,  default=False)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True, null=True)
    hours = models.FloatField(blank=True,null=True)
    #date = models.DateField()
    date = models.DateField(null=True, blank=True)
    phone1 = models.CharField(max_length=12, default="unknown")
    full_address = models.CharField(max_length=100, default="unknown")
    #date_of_birth = models.DateField()
    date_of_birth = models.DateField(null=True, blank=True)
    wear_mask = models.BooleanField(blank=True,  default=False)
    waiver = models.BooleanField(blank=True,  default=False)
    ice_name = models.CharField(max_length=100, default="unknown")
    ice_relationship = models.CharField(max_length=100, default="unknown")
    ice_phone = models.CharField(max_length=12, default="unknown")
    allergies =  models.CharField(max_length=100, blank=True, null=True, default="none")
    email_blocked = models.BooleanField(default=False)
    makeup = models.BooleanField(default=False)
    costume = models.BooleanField(default=False)




    event = models.ForeignKey('Events', models.DO_NOTHING)

    class Meta:
        """
        Meta class for EventVolunteers.
        It specifies the database table name
            and that this model is not managed by Django migrations.
        """
        # This model is managed by the database, not Django migrations
        # This means that Django will not create or modify the table for this model
        # It is typically used for legacy tables or when the table is managed by another system
        # or when you want to prevent Django from making changes to the table structure.
        # This is useful when you have a pre-existing table that you want to use with Django models.
        # It allows you to define a model that maps to an existing table without Django
        # trying to manage it.
        #
        db_table = 'event_volunteers'
        ordering = ['date']

    def __str__(self):
        return f"{self.volunteer.email} - {self.event.event_name} - {self.task}"

