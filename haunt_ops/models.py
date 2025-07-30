from django.contrib.auth.models import AbstractUser
from django.contrib.auth.base_user import BaseUserManager
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
# we have a custom user table so lets get the table name from the settings file
from django.conf import settings
import datetime

from django.db import models


class AppUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        extra_fields = {"is_staff": False, "is_superuser": False, "is_active": True, **extra_fields}
        if not email:
            raise ValueError("Users must provide an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields = {**extra_fields, "is_staff": True, "is_superuser": True, "is_active": True}
        return self.create_user(email=email, password=password, **extra_fields)



class AppUser(AbstractUser):
        email = models.CharField(max_length=150, unique=True)
        username = models.CharField(max_length=150, unique=True)
        image_url = models.CharField(max_length=200, blank=True, null=True)
        tshirt_size = models.CharField(max_length=12, default="unknown")
        address = models.CharField(max_length=100, default="unknown")
        city = models.CharField(max_length=100, blank=True, null=True)
        state = models.CharField(max_length=30, default="CA")
        zipcode = models.CharField(max_length=20, default="unknown")
        country = models.CharField(max_length=30, default="USA")
        company = models.CharField(max_length=100, blank=True, null=True)
        phone1 = models.CharField(max_length=12, default="unknown")
        phone2 = models.CharField(max_length=12, blank=True, null=True)
        date_of_birth = models.DateField(null=True)
        last_activity = models.DateTimeField(blank=True, null=True)
        email_blocked = models.BooleanField(default=False)
        ice_name = models.CharField(max_length=100, default="unknown")
        ice_relationship = models.CharField(max_length=100, default="unknown")
        ice_phone = models.CharField(max_length=12, default="unknown")
        wear_mask = models.BooleanField(default=False)
        referral_source =  models.CharField(max_length=500,  blank=True, null=True)
        haunt_experience =  models.CharField(max_length=500,  blank=True, null=True)
        allergies =  models.CharField(max_length=100, blank=True, null=True)
        waiver = models.BooleanField(default=False)
        point_total = models.IntegerField(default=0)



        USERNAME_FIELD = 'email'
        # required fields is only used when running createsuperuser
        REQUIRED_FIELDS = ['username']

        objects = AppUserManager()

        class Meta:
            db_table = 'app_user'

        def __str__(self):
            return self.email

class Groups(models.Model) :
      group_name = models.CharField(max_length=100, unique=True)
      group_points = models.IntegerField(default=1)

      class Meta:
            db_table = 'groups'

      def __str__(self):
          return self.group_name or "Unnamed Group"

class GroupVolunteers(models.Model) :
      volunteer = models.ForeignKey(settings.AUTH_USER_MODEL,
                  on_delete=models.CASCADE)
      group = models.ForeignKey(Groups, 
              on_delete=models.CASCADE)

      class Meta:
            db_table = 'group_volunteers'

      def __str__(self):
          return self.group.name or "Unnamed Group"

class Events(models.Model) :
      event_date = models.DateField(null=True,blank=True)
      event_name = models.CharField(max_length=500, blank=True)
      event_status = models.TextField(max_length=50, default="TBD")
      class Meta:
            db_table = 'events'

      def __str__(self):
          return f"{self.event_name or 'Unnamed Event'} on {self.event_date.date() if self.event_date else 'TBD'}"

class EventVolunteers(models.Model):
      id = models.BigAutoField(primary_key=True)
      start_time = models.DateTimeField(blank=True, null=True)
      end_time = models.DateTimeField(blank=True, null=True)
      volunteer = models.ForeignKey(AppUser, models.DO_NOTHING)
      task = models.TextField()
      slot_column = models.TextField(blank=True, null=True)
      slot_row = models.TextField(blank=True, null=True)
      signed_in = models.BooleanField(blank=True, null=True)
      conflict = models.BooleanField(blank=True, null=True)
      confirmed = models.BooleanField(blank=True, null=True)
      waitlist = models.BooleanField(blank=True, null=True)
      points = models.FloatField(blank=True, null=True)
      event_name = models.TextField()
      event = models.ForeignKey('Events', models.DO_NOTHING)

      class Meta:
          managed = False
          db_table = 'event_volunteers'

      def __str__(self):
          return f"{self.volunteer.email} - {self.event.event_name} - {self.group_name}"

class EventChecklist(models.Model) :
      volunteer = models.ForeignKey(settings.AUTH_USER_MODEL,
                  on_delete=models.CASCADE)
      group = models.ForeignKey(Groups,
              on_delete=models.CASCADE)
      event = models.ForeignKey(Events,
              on_delete=models.CASCADE)

      signed_in = models.BooleanField(default=False)
      costume = models.BooleanField(default=False)
      makeup = models.BooleanField(default=False)
      trained =  models.BooleanField(default=False)

      class Meta:
            db_table = 'event_checklist'

      def __str__(self):
          return f"Checklist: {self.volunteer.email} for {self.event.event_name}"
