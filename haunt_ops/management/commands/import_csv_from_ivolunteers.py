from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime
from haunt_ops.models import AppUser
import csv

class Command(BaseCommand):

    help = 'Load ivolunteer users from CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str)

    def handle(self, *args, **kwargs):
        file_path = kwargs['csv_file']
        with open(file_path, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            user_email=''
            for row in reader:
                user_email = row['email']

                original_bd=row['date_of_birth'].strip()
                print(f"original birth date {original_bd}")

                bd=original_bd.split(' ',1)
                print(f"date_of_birth after split {bd[0]}")

                dj=row['start_date'].strip()
                print(f"naive_date_joined before tz added {dj}")

                naive_dt = datetime.strptime(dj, '%Y-%m-%d %H:%M:%S') 
                aware_dj=timezone.make_aware(naive_dt, timezone=timezone.get_current_timezone())
                print(f"aware_date_joined after tz added {aware_dj}")


                print(f"waiver: {row['waiver']}")
                wv=False
                if "I agree" in row['waiver'].strip() :
                    wv=True
                else:
                    wv=False
                print(f"waiver after test: {wv}")

                print(f"email_blocked: {row['email_blocked']}")
                eb=False
                if "true" in row['email_blocked'].strip().lower() :
                    eb=True
                else:
                    eb=False
                print(f"email_blocked after test: {eb}")

                print(f"wear_mask: {row['wear_mask']}")
                wm=False
                if "true" in row['wear_mask'].strip().lower() :
                    wm=True
                else:
                    wm=False
                print(f"wear_mask after test: {wm}")

                AppUser.objects.create_user(
                    first_name=row['first_name'].strip(),
                    last_name=row['last_name'].strip(),
                    email=row['email'].strip(),
                    username=row['email'].strip(),
                    company=row['company'].strip(),
                    address=row['address'].strip(),
                    city=row['city'].strip(),
                    state=row['state'].strip(),
                    zipcode=row['zipcode'].strip(),
                    country=row['country'].strip(),
                    phone1=row['phone1'].strip(),
                    phone2=row['phone2'].strip(),
                    #under_18=row['under_18'].strip()
                    date_of_birth=bd[0],
                    password=bd[0],
                    #notes=row['notes'].strip(),
                    date_joined=aware_dj,
                    #last_activity=row['last_activity'].strip(),
                    waiver=wv,
                    referral_source=row['referral_source'].strip(),
                    haunt_experience=row['haunt_experience'].strip(),
                    wear_mask=wm,
                    tshirt_size=row['tshirt_size'].strip(),
                    ice_name=row['ice_name'].strip(),
                    ice_relationship=row['ice_relationship'].strip(),
                    ice_phone=row['ice_phone'].strip(),
                    allergies=row['allergies'].strip(),
                    email_blocked=eb,
                    #groups=row['groups'].strip()
                    #events=row['events'].strip()
                )
                print(f"successfully create user {user_email}.")
        self.stdout.write(self.style.SUCCESS('CSV import complete.'))

