# haunt_ops/management/commands/passage_ticket_sales_query.py
import os
import re
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional
from dateutil import parser, tz as dtu_tz

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

# If these utils live elsewhere, adjust the imports:
from haunt_ops.utils.passage_utils import (
    chrome_session,
    login_passage,
    go_to_events_upcoming,
    scrape_upcoming_events_paginated,
)

# Fallback bounds when only a date is known
DEFAULT_START = time(0, 0, 0)
DEFAULT_END = time(23, 59, 59)
PACIFIC = dtu_tz.gettz("America/Los_Angeles")



def parse_passage_dt(s: str):
    tzinfos = {"PDT": PACIFIC, "PST": PACIFIC}
    dt_local = parser.parse(s, tzinfos=tzinfos)
    if dt_local.tzinfo is None:
        dt_local = dt_local.replace(tzinfo=PACIFIC)
    return dt_local.astimezone(timezone.utc)



def _tz_from_label(label: Optional[str]) -> ZoneInfo:
    """
    Map GoPassage time zone labels to IANA timezones.
    Defaults to America/Los_Angeles if 'Pacific' or unknown.
    """
    if not label:
        return ZoneInfo("America/Los_Angeles")
    lab = label.lower()
    if "pacific" in lab:
        return ZoneInfo("America/Los_Angeles")
    if "mountain" in lab:
        return ZoneInfo("America/Denver")
    if "central" in lab:
        return ZoneInfo("America/Chicago")
    if "eastern" in lab:
        return ZoneInfo("America/New_York")
    return ZoneInfo("America/Los_Angeles")


def _coerce_int(val: Any, default_if_none: int = 0) -> int:
    """
    Convert 'N/A'/'None'/''/None to default_if_none, otherwise int().
    """
    if val is None:
        return default_if_none
    if isinstance(val, int):
        return val
    s = str(val).strip()
    if not s or s.upper() == "N/A":
        return default_if_none
    try:
        return int(float(s))
    except Exception:
        return default_if_none


def _parse_event_date(val: Any) -> Optional[datetime.date]:
    """
    Accept several formats for event_date:
      - date object
      - 'YYYY-MM-DD'
      - 'Friday, September 26, 2025'
      - '9/26/2025'
    """
    if val is None:
        return None
    if hasattr(val, "year") and hasattr(val, "month") and hasattr(val, "day"):
        return val

    s = str(val).strip()

    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        pass

    for fmt in ("%A, %B %d, %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue

    return None


class Command(BaseCommand):
    help = "Login to GoPassage, open Events→Upcoming, scrape ticket sales (paginated), and upsert into TicketSales."

    def add_arguments(self, parser):
        parser.add_argument(
            "--headed",
            action="store_true",
            default=False,
            help="Run the browser headed (default is headless).",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=30,
            help="Max seconds to wait for elements/navigation.",
        )
        parser.add_argument(
            "--max-pages",
            type=int,
            default=20,
            help="Maximum number of Upcoming pages to scrape.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Only print scraped rows, do not write to DB.",
        )

    def handle(self, *args, **opts):
        username = os.environ.get("GOPASSAGE_EMAIL")
        password = os.environ.get("GOPASSAGE_PASSWORD")
        gopassage_url = os.environ.get(
            "GOPASSAGE_URL", "https://app.gopassage.com/users/sign_in"
        )
        if not username or not password:
            raise CommandError("Set GOPASSAGE_EMAIL and GOPASSAGE_PASSWORD env vars.")

        headed = bool(opts["headed"])
        timeout = int(opts["timeout"])
        max_pages = int(opts["max_pages"])
        dry_run = bool(opts["dry_run"])

        with chrome_session(headless=not headed) as driver:
            login_passage(driver, username, password, gopassage_url, timeout=timeout)
            go_to_events_upcoming(driver, timeout=timeout)
            rows: List[Dict[str, Any]] = scrape_upcoming_events_paginated(
                driver, timeout=timeout, max_pages=max_pages
            )

        # Show what we scraped (always)
        for r in rows:
            self.stdout.write(str(r))

        if dry_run:
            self.stdout.write(self.style.WARNING("Print-only mode: no DB writes."))
            return

        TicketSales = apps.get_model("haunt_ops", "TicketSales")
        Events = apps.get_model("haunt_ops", "Events")

        upserts = 0
        links = 0
        created_events = 0
        skipped_bad_date = 0

        @transaction.atomic
        def do_upserts(scraped_rows: List[Dict[str, Any]]):
            nonlocal upserts, links, created_events, skipped_bad_date

            for row in scraped_rows:
                # Expected keys (varying presence):
                # event_time_id / id, event_name, event_date
                # start_time, end_time,
                # tickets_purchased, tickets_remaining
                event_time_id = row.get("event_time_id") or row.get("id")
                event_name_raw = (row.get("event_name") or "").strip()
                local_tz = _tz_from_label(row.get("time_zone"))  # ZoneInfo
                start_text = row.get("start_time")
                end_text   = row.get("end_time")
                self.stdout.write(f"start={start_text} end={end_text} tz={local_tz}")
                start_dt_utc = None
                end_dt_utc = None
                event_date = None

                # Prefer ISO start/end for precision
                if start_text:
                    start_dt_utc = parse_passage_dt(start_text)
                if end_text:
                    end_dt_utc = parse_passage_dt(end_text)

                if not start_dt_utc or not end_dt_utc:
                    self.stdout.write(self.style.WARNING(
                        f"[parse-miss] id={row.get('event_time_id') or row.get('id')} "
                        f"date={row.get('event_date')} start='{row.get('start_time')}' "
                        f"end='{row.get('end_time')}'"
                    ))


                # Determine event_date from start_dt if possible; else parse the scraped label
                if start_dt_utc:
                    event_date = start_dt_utc.astimezone(local_tz).date()
                else:
                    event_date = _parse_event_date(row.get("event_date"))

                if not event_date:
                    skipped_bad_date += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipping row — bad/unknown event_date: {row.get('event_date')}"
                        )
                    )
                    continue

                # Build final start/end if missing
                event_start_time = (
                    start_dt_utc
                    if start_dt_utc
                    else datetime.combine(event_date, DEFAULT_START, tzinfo=local_tz).astimezone(timezone.utc)
                )
                event_end_time = (
                    end_dt_utc
                    if end_dt_utc
                    else datetime.combine(event_date, DEFAULT_END, tzinfo=local_tz).astimezone(timezone.utc)
                )

                tickets_purchased = _coerce_int(row.get("tickets_purchased"), default_if_none=0)
                tickets_remaining = _coerce_int(row.get("tickets_remaining"), default_if_none=0)

                # Resolve FK to Events by same date; create if missing.
                evt = None
                evt_qs = Events.objects.filter(event_date=event_date)
                if evt_qs.exists():
                    # Try to match by name; fallback to first on that date.
                    if event_name_raw:
                        evt = (
                            evt_qs.filter(
                                Q(event_name__iexact=event_name_raw)
                                | Q(event_name__icontains=event_name_raw)
                                | Q(event_name__in=[event_name_raw])
                            ).first()
                            or evt_qs.first()
                        )
                    else:
                        evt = evt_qs.first()
                else:
                    # Create a new Event using the TicketSales date; make name unique via date.
                    # If event_name_raw is present, keep it and suffix the ISO date; else use a generic prefix.
                    base_name = event_name_raw if event_name_raw else "GoPassage Event"
                    new_name = f"{base_name} — {event_date.isoformat()}"
                    evt = Events.objects.create(
                        event_name=new_name,
                        event_date=event_date,
                    )
                    created_events += 1
                    self.stdout.write(self.style.SUCCESS(f"Created Events row: '{new_name}' ({event_date})"))

                # Use source_event_time_id as natural key when present
                if event_time_id is not None:
                    ts, _created = TicketSales.objects.update_or_create(
                        source_event_time_id=int(event_time_id),
                        defaults={
                            "event_name": event_name_raw or evt.event_name,
                            "event_date": event_date,
                            "event_start_time": event_start_time,
                            "event_end_time": event_end_time,
                            "tickets_purchased": tickets_purchased,
                            "tickets_remaining": tickets_remaining,
                            "event_id": evt,
                        },
                    )
                else:
                    # Fallback approximate key
                    ts, _created = TicketSales.objects.update_or_create(
                        event_id=evt,
                        event_date=event_date,
                        event_name=event_name_raw or evt.event_name,
                        defaults={
                            "event_start_time": event_start_time,
                            "event_end_time": event_end_time,
                            "tickets_purchased": tickets_purchased,
                            "tickets_remaining": tickets_remaining,
                        },
                    )

                upserts += 1

                # Ensure FK is linked (defensive)
                if getattr(ts, "event_id_id", None) != evt.id:
                    ts.event_id = evt
                    ts.save(update_fields=["event_id"])
                    links += 1

        do_upserts(rows)

        self.stdout.write(
            self.style.SUCCESS(
                f"Upserts: {upserts}; Linked to Events: {links}; "
                f"Created Events: {created_events}; Skipped (bad date): {skipped_bad_date}"
            )
        )
