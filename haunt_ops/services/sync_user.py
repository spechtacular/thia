"""
Docstring for haunt_ops.services.sync_user
"""

#import logging
from django.utils import timezone
from haunt_ops.models import AppUser, Groups, GroupVolunteers
from haunt_ops.utils.time_string_utils import to_date,safe_parse_datetime

from haunt_ops.utils.safe_utils import (
    safe_strip,
    safe_bool,
    safe_float
)

#logger = logging.getLogger("haunt_ops")


def sync_user(data, logger, dry_run=False):
    """
    Create or update an AppUser based on normalized user data (JSON or CSV).
    Assumes column names are already mapped using etl_config.yaml.
    """
    email = safe_strip(data.get("email"))
    if not email:
        logger.warning("⚠️ Skipping user with missing email")
        return None

    try:
        defaults = {
            "first_name": safe_strip(data.get("first_name")),
            "last_name": safe_strip(data.get("last_name")),
            "username": email,
            "company": safe_strip(data.get("company")),
            "address": safe_strip(data.get("address")),
            "city": safe_strip(data.get("city")),
            "state": safe_strip(data.get("state") or "CA"),
            "zipcode": safe_strip(data.get("zipcode")),
            "country": safe_strip(data.get("country") or "USA"),
            "phone1": safe_strip(data.get("phone1")) or "unknown",
            "phone2": safe_strip(data.get("phone2")),
            "email_blocked": safe_bool(data.get("email_blocked")),
            "ice_name": safe_strip(data.get("ice_name")),
            "ice_relationship": safe_strip(data.get("ice_relationship")),
            "ice_phone": safe_strip(data.get("ice_phone")),
            "referral_source": safe_strip(data.get("referral_source")),
            "tshirt_size": safe_strip(data.get("tshirt_size") or "Unknown"),
            "allergies": safe_strip(data.get("allergies") or "none"),
            "wear_mask": safe_bool(data.get("wear_mask")),
            "waiver": safe_bool(data.get("waiver")),
            "haunt_experience": safe_strip(data.get("haunt_experience")),
            "point_total": safe_float(data.get("points") or 0.0),
            "safety_class": safe_bool(data.get("safety_class")),
            "line_actor_training": safe_bool(data.get("line_actor_training")),
            "room_actor_training": safe_bool(data.get("room_actor_training")),
            "costume_size": safe_strip(data.get("costume_size") or "Unknown"),
        }

        # Parse and assign date fields
        dob = safe_parse_datetime(data.get("date_of_birth"))
        if dob:
            defaults["date_of_birth"] = to_date(dob)
        else:
            logger.debug("⚠️ Missing or invalid date_of_birth for %s", email)

        joined = safe_parse_datetime(data.get("start_date"))
        if joined:
            defaults["date_joined"] = (
                joined if timezone.is_aware(joined) else timezone.make_aware(joined)
            )

        last_activity = safe_parse_datetime(data.get("last_activity"))
        if last_activity:
            defaults["last_activity"] = last_activity

        if dry_run:
            logger.info("ℹ️ DRY RUN: Would create/update AppUser %s", email)
            return None

        logger.debug("Creating user %s with: %s", email, defaults)

        try:
            user, created = AppUser.objects.update_or_create(email=email, defaults=defaults)
            logger.info("✅ %s user %s", "Created" if created else "Updated", email)

        except (ValueError, TypeError) as e:
            logger.warning("⚠️ Error creating/updating AppUser %s: %s", email, str(e))
            return None


        # --- Groups ---
        group_string = data.get("groups", "")
        group_names = [g.strip() for g in group_string.split(",") if g.strip()]
        for group_name in group_names:
            group, _ = Groups.objects.get_or_create(
                group_name__iexact=group_name,
                defaults={"group_name": group_name}
            )
            GroupVolunteers.objects.get_or_create(volunteer=user, group=group)
            logger.debug("🔗 Linked %s to group %s", email, group_name)

        return created

    except (ValueError, TypeError, AttributeError) as e:
        logger.warning("⚠️ Error processing record %s: %s", email, str(e))
        return None
