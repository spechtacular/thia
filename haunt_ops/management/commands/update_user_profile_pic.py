"""
This command updates a user profile based on users email address.
It allows updating user fields : image_url only, for now
It assigns an image url based on image file names in the specified image directory.
"""

import os

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from haunt_ops.models import AppUser
from haunt_ops.utils.logging_utils import configure_rotating_logger


# pylint: disable=no-member



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
            default="static/people_pics",
            help="pass the path to the people_pics directory containing volunteer images.",
        )

        parser.add_argument(
            "--log",
            type=str,
            default="INFO",
            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            help="Set the log level (default: INFO)",
        )

        parser.add_argument(
            "--image_url",
            type=str,
            help="Update image_url field in app_user table",
            default="image_url"
        )

        parser.add_argument(
            "--dry-run", action="store_true", help="Preview changes without saving them"
        )

    def process_file_name(self, imagefile, user, logger):
        """
        Process the image file name to match user first and last names.
        Returns the image file name if it matches the user's first and last names.
        """
        filename, ext = os.path.splitext(imagefile)
        logger.info("Processing people_pics file: %s", {imagefile})
        allowed_extensions = {".jpg", ".jpeg", ".png"}
        # convert user first and last names to lower case and remove weird characters
        fname = user.first_name.lower().replace("'", "").replace('"', "")
        lname = user.last_name.lower().replace("'", "_").replace('"', "")
        # convert image file name to lower case
        ifile = imagefile.lower()

        logger.info("Processing people_pics file: %s,%s,%s", {ifile},{fname},{lname})

        if fname in ifile and lname in ifile:
            name, ext = os.path.splitext(ifile)

            if ext not in allowed_extensions:
                logger.info("Skipping unsupported file type: %s", {filename})
                return None

            return imagefile

        return None

    def handle(self, *args, **options):
        email = options["email"]
        dry_run = options["dry_run"]
        image_directory = options["image_directory"]
        field = options["image_url"]
        log_level = options["log"].upper()

         # Get a unique log file using __file__
        logger = configure_rotating_logger(
            __file__, log_dir=settings.LOG_DIR, log_level=log_level
        )


        try:
            user = AppUser.objects.get(email=email)
        except AppUser.DoesNotExist:  # pylint: disable=no-member
            logger.error("User with email %s not found.",{email})
            return

        # Print user ID
        logger.info("Found user ID: %s, searching image directory %s", {user.id}, {image_directory})

        # Update fields if provided
        fields_updated = False
        for field in ["first_name", "last_name", "phone1", "phone2", "image_url"]:
            new_value = options.get(field)

            if new_value is not None:
                logger.info("User with email %s updating %s", {email}, {field})
                if field == "image_url":
                    image_path = image_directory
                    if not os.path.isdir(image_path):
                        raise CommandError(
                            f'Directory "{image_path}" does not exist.'
                        )

                    logger.info("Processing files in: %s", {image_path})

                    for filename in os.listdir(image_path):
                        file_path = os.path.join(image_path, filename)
                        if os.path.isfile(file_path):
                            pic_file_found = self.process_file_name(filename, user, logger)
                            if pic_file_found is not None:
                                logger.info(
                                        "found image_url %s for %s ", {pic_file_found}, {file_path}
                                    )
                                setattr(user, "image_url", pic_file_found)
                                fields_updated = True
                                break

                        if fields_updated:
                            logger.info("File processing for user %s complete.", {email})
                        else:
                            logger.error("no matching image for user %s", {email})

                else:
                    # not updating the image_url fields
                    setattr(user, field, options[field])
                    fields_updated = True

        if fields_updated:
            if not dry_run:
                user.save()
                logger.info("Updated profile for %s", {email})
            else:
                logger.warning("Dry run enabled — no app_user fields saved.")
        else:
            logger.info("No fields provided to update.")
