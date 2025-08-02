"""
This command updates a user profile based on users email address.
It allows updating user fields : first name, last name, phone numbers,
and optionally assigns an image url based on image files in the specified image directory.
"""

import os
from django.core.management.base import BaseCommand, CommandError
from haunt_ops.models import AppUser


class Command(BaseCommand):
    """
    start command
        python manage.py update_user_profile_pic
    """

    help = "Update a user profile by email address"

    def add_arguments(self, parser):

        parser.add_argument("email", type=str, help="Email address of the user")

        parser.add_argument(
            "--image_directory",
            type=str,
            help="pass the path to the people_pics directory containing volunteer images.",
            default=None,
        )

        parser.add_argument("--first_name", type=str, help="First name", default=None)
        parser.add_argument("--last_name", type=str, help="Last name", default=None)
        parser.add_argument("--phone1", type=str, help="Phone number", default=None)
        parser.add_argument("--phone2", type=str, help="Phone number", default=None)
        parser.add_argument("--image_url", type=str, help="Image URL", default=None)

        parser.add_argument(
            "--dry-run", action="store_true", help="Preview changes without saving them"
        )

    def process_file_name(self, imagefile, user):
        """
        Process the image file name to match user first and last names.
        Returns the image file name if it matches the user's first and last names.
        """
        filename, ext = os.path.splitext(imagefile)
        self.stdout.write(f"Processing people_pics file: {imagefile}")
        allowed_extensions = {".jpg", ".jpeg", ".png"}
        # Add your custom logic here, e.g.,
        # - Parse information from the filename
        # - Perform database operations based on the filename
        # - Rename the file
        # - etc.
        fname = user.first_name.lower().replace("'", "").replace('"', "")
        lname = user.last_name.lower().replace("'", "_").replace('"', "")
        ifile = imagefile.lower()

        self.stdout.write(f"Processing people_pics file: {ifile},{fname},{lname}")
        if fname in ifile and lname in ifile:
            name, ext = os.path.splitext(ifile)

            if ext not in allowed_extensions:
                self.stdout.write(f"Skipping unsupported file type: {filename}")
                return None

            return imagefile

        return None

    def handle(self, *args, **options):
        email = options["email"]
        dry_run = options["dry_run"]

        try:
            user = AppUser.objects.get(email=email)
        except AppUser.DoesNotExist:  # pylint: disable=no-member
            self.stderr.write(
                self.style.ERROR(f"User with email {email} not found.")
            )  # pylint: disable=no-member
            return

        # Print user ID
        self.stdout.write(f"Found user ID: {user.id}")

        # Update fields if provided
        fields_updated = False
        for field in ["first_name", "last_name", "phone1", "phone2", "image_url"]:
            new_value = options.get(field)

            if new_value is not None:
                self.stderr.write(
                    self.style.SUCCESS(f"User with email {email} updating {field}")
                )  # pylint: disable=no-member
                if field == "image_url":
                    image_path = options["image_directory"]
                    if not os.path.isdir(image_path):
                        raise CommandError(
                            f'Directory "{image_path}" does not exist.'
                        )  # pylint: disable=no-member

                    self.stdout.write(
                        self.style.SUCCESS(f"Processing files in: {image_path}")
                    )  # pylint: disable=no-member

                    for filename in os.listdir(image_path):
                        file_path = os.path.join(image_path, filename)
                        if os.path.isfile(file_path):
                            pic_file_found = self.process_file_name(filename, user)
                            if pic_file_found is not None:
                                self.stdout.write(
                                    self.style.SUCCESS(
                                        f"found image_url {pic_file_found} for {email} ."
                                    )
                                )  # pylint: disable=no-member
                                setattr(user, "image_url", pic_file_found)
                                fields_updated = True
                                break

                        if fields_updated:
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"File processing for user {email} complete."
                                )
                            )
                        else:
                            self.stdout.write(
                                self.style.ERROR(
                                    f'no matching image for user {email}".'
                                )
                            )  # pylint: disable=no-member

                else:
                    # not updating the image_url fields
                    setattr(user, field, options[field])
                    fields_updated = True

        if fields_updated:
            if not dry_run:
                user.save()
                self.stdout.write(self.style.SUCCESS(f"Updated profile for {email}"))
            else:
                self.stdout.write(
                    self.style.WARNING("Dry run enabled — no changes saved.")
                )
        else:
            self.stdout.write("No fields provided to update.")
