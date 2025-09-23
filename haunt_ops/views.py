"""
This file contains views for the HauntOps application.
It includes views for user profiles, signup, and the home page.
"""
import logging
from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.contrib.auth import logout
from django.db.models import Count
from django.urls import reverse
from django.db.models.functions import Coalesce
from django.utils.http import url_has_allowed_host_and_scheme
from django.db.models import Sum, Min, Max
from datetime import date, datetime


from .forms import PublicSignupForm, AppUserChangeForm
from .forms import EventPrepForm, UserPrepForm

from .models import AppUser, Events, Groups, EventVolunteers, GroupVolunteers, TicketSales


# use for debugging only
logger = logging.getLogger(__name__)

def signup(request):
    """
    View for handling user signup.
    It uses the PublicSignupForm to create a new user.
    If the form is valid, it saves the user and redirects to the login page.
    """
    if request.method == 'POST':
        form = PublicSignupForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')  # redirect after signup
    else:
        form = PublicSignupForm()
    return render(request, 'registration/signup.html', {'form': form})


def home(request):
    """
    View for the home page of the HauntOps application.
    It renders the home template.
    """
    return render(request, 'home.html')


@login_required
def profile_view(request):
    """
    View for displaying and editing the user's profile.
    It uses the AppUserChangeForm to handle profile updates.
    If the form is valid, it saves the changes and redirects to the same page.
    """
    if request.method == 'POST':
        form = AppUserChangeForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('profile')  # stay on the same page after saving
    else:
        form = AppUserChangeForm(instance=request.user)

    return render(request, 'profile.html', {'form': form})


def login_view(request):
    """
    View for handling user login.
    It authenticates the user and redirects to their public profile if successful.
    If the credentials are invalid, it renders the login template with an error message.
    """
    if request.method == 'POST':
        email = request.POST.get('username')  # the login form field is still "username"
        password = request.POST.get('password')
        user = authenticate(request, username=email, password=password)
        if user:
            login(request, user)
            return redirect('profile')
        else:
            return render(request, 'registration/login.html', {
                'form_error': 'Invalid email or password.'
            })

    return render(request, 'registration/login.html')



def public_profile(request, username):
    """
    View for displaying a public profile of a user.
    It retrieves the user by username and renders the public profile template.
    If the user does not exist, it raises a 404 error.
    """
    user = get_object_or_404(AppUser, username=username)
    return render(request, 'public_profile.html', {'user_profile': user})



def user_list(request):
    """
    list users from app_user table
    """
    qs = (
        AppUser.objects
        .annotate(
            groups_count=Count('group_volunteers_as_volunteer', distinct=True),  # FK/M2M on related model pointing to User
            events_count=Count('event_participants', distinct=True),  # same idea
        )
        .order_by('last_name', 'first_name')
    )
    paginator = Paginator(qs, 25)
    page = request.GET.get('page')
    try:
        users_page = paginator.page(page)
    except PageNotAnInteger:
        users_page = paginator.page(1)
    except EmptyPage:
        users_page = paginator.page(paginator.num_pages)
    return render(request, 'haunt_ops/user_list.html', {'users_page': users_page})


def event_volunteers_list(request):
    """
    View for listing all event volunteers.
    It retrieves all event volunteers from the database and paginates them."""
    evols = EventVolunteers.objects.all().order_by('date')
    # Paginate with 20 event volunteers per page
    paginator = Paginator(evols, 25)
    page = request.GET.get('page', 1)

    try:
        evols_page = paginator.page(page)
    except PageNotAnInteger:
        evols_page = paginator.page(1)
    except EmptyPage:
        evols_page = paginator.page(paginator.num_pages)

    return render(request, 'haunt_ops/event_volunteers_list.html', {
        'evols_page': evols_page
    })

def group_volunteers_list(request):
    """
    correlate volunteers with groups they have experience with
    """
    # Pull related user & group in one query
    qs = (GroupVolunteers.objects
          .select_related('volunteer', 'group')
          .order_by('group__group_name', 'volunteer__last_name', 'volunteer__first_name'))

    paginator = Paginator(qs, 25)  # 25 rows per page
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    return render(request, 'haunt_ops/group_volunteers_list.html', {
        'page_obj': page_obj,
    })


def events_list(request):
    """
    View for listing all events.
    It retrieves all events from the database and paginates them.
    """
    events = Events.objects.all().order_by('event_date')
    # Paginate with 10 events per page
    paginator = Paginator(events, 25)
    page = request.GET.get('page', 1)

    try:
        events_page = paginator.page(page)
    except PageNotAnInteger:
        events_page = paginator.page(1)
    except EmptyPage:
        events_page = paginator.page(paginator.num_pages)

    return render(request, 'haunt_ops/events_list.html', {
        'events_page': events_page
    })

def groups_list(request):
    """
    View for listing all groups.
    It retrieves all groups from the database and paginates them.
    """
    groups = (
        Groups.objects
        .annotate(volunteer_count=Count("group_volunteers"))  # adjust related name!
        .order_by("group_name")
    )

    # Paginate with 10 groups per page
    paginator = Paginator(groups, 25)
    page = request.GET.get('page', 1)

    try:
        groups_page = paginator.page(page)
    except PageNotAnInteger:
        groups_page = paginator.page(1)
    except EmptyPage:
        groups_page = paginator.page(paginator.num_pages)

    return render(request, 'haunt_ops/groups_list.html', {
        'groups_page': groups_page
    })


def user_detail(request, pk):
    """
    View for displaying the details of a specific user.
    It retrieves the user by primary key (pk) and renders the user detail template.
    If the user does not exist, it raises a 404 error.
    """
    user = get_object_or_404(AppUser, pk=pk)
    return render(request, "haunt_ops/user_detail.html",
                  {"user": user,
                    "back_url": request.META.get("HTTP_REFERER", reverse("user_list")),
                })


@login_required
def event_detail(request, pk):
    """
    Page that lists all volunteers for a specific event,
    and shows a quick-inline EventPrepForm on the far right per volunteer.
    """
    event = get_object_or_404(Events, pk=pk)

    # All volunteers for this event (ordered by volunteer name)
    signups = (
        EventVolunteers.objects
        .filter(event=event)
        .select_related('volunteer')
        .order_by('volunteer__last_name', 'volunteer__first_name')
    )

    # Build a per-row EventPrepForm (no prefix; each form is in its own <form>)
    for ev in signups:
        ev.ev_form = EventPrepForm(instance=ev)

    # Validate the caller-provided return URL; fall back to events_list
    return_to = request.GET.get("return_to")
    if not return_to or not url_has_allowed_host_and_scheme(
        url=return_to,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return_to = reverse("events_list")

    return render(request, 'haunt_ops/event_detail.html', {
        'event': event,
        'signups': signups,
        'return_to': return_to,
    })


def event_prep_quick_update(request, event_pk, vol_pk):
    """
    Lightweight POST endpoint to update only EventVolunteers flags
    from the inline form on the event_detail page.
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    event = get_object_or_404(Events, pk=event_pk)
    ev_signup = get_object_or_404(
        EventVolunteers.objects.select_related("event"),
        pk=vol_pk,
    )
    if ev_signup.event_id != event.pk:
        raise Http404("Volunteer signup does not belong to this event.")

    form = EventPrepForm(request.POST, instance=ev_signup)
    if form.is_valid():
        form.save()

    # optional: respect ?return_to=...
    next_url = request.POST.get("return_to") or reverse("event_detail", kwargs={"pk": event_pk})
    # prevent open redirect
    if not url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = reverse("event_detail", kwargs={"pk": event_pk})

    return redirect(next_url)


@login_required
def event_prep(request, event_pk, vol_pk):
    """
    Page related to each volunteers prep for a specific event
    """
    event  = get_object_or_404(Events, pk=event_pk)
    ev_signup = get_object_or_404(
        EventVolunteers.objects.select_related('volunteer','event'),
        pk=vol_pk, event_id=event_pk
    )
    user = ev_signup.volunteer

    if request.method == 'POST':
        user_form = UserPrepForm(request.POST, instance=user)
        ev_form = EventPrepForm(request.POST, instance=ev_signup)
        if user_form.is_valid() and ev_form.is_valid():
            user_form.save()
            ev_form.save()
            return redirect('event_detail', pk=event_pk)
    else:
        ev_form = EventPrepForm(instance=ev_signup)
        user_form = UserPrepForm(instance=user)


    return render(request, 'event_prep.html', {
        'event':  event,
        'ev_signup': ev_signup,
        'user':   ev_signup.volunteer,
        'user_form':   user_form,
        'ev_form':     ev_form,
    })

def _as_date(value):
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return value.date()
    except Exception:
        return None


def _age_at_least(dob, years, ref_date):
    if not dob or not ref_date:
        return None
    age = ref_date.year - dob.year - ((ref_date.month, ref_date.day) < (dob.month, dob.day))
    return age >= years

def event_prep_view(request, event_pk, vol_pk):
    """
    Page related to each volunteer's prep for a specific event.

    URL is called with:
      - event_pk = Events.pk
      - vol_pk   = EventVolunteers.pk  (NOT AppUser.pk)
    """
    event = get_object_or_404(Events, pk=event_pk)
    # pick the specific signup row; if multiples exist, you may want filter(...) + select one explicitly
    ev_signup = get_object_or_404(
        EventVolunteers.objects.select_related('volunteer','event'),
        pk=vol_pk, event_id=event_pk
    )

    if ev_signup.event_id != event.pk:
        raise Http404("Volunteer signup does not belong to this event.")

    user = ev_signup.volunteer  # AppUser instance

    # Use prefixes to avoid any naming collisions between two forms
    user_prefix = "user"
    ev_prefix = "ev"


    if request.method == "POST":
        user_form = UserPrepForm(request.POST, instance=user, prefix=user_prefix)
        ev_form = EventPrepForm(request.POST, instance=ev_signup, prefix=ev_prefix)

        if user_form.is_valid() and ev_form.is_valid():
            with transaction.atomic():
                user_form.save()
                # ev_form.save()  # do below instead
                saved_ev = ev_form.save(commit=False)
                # Force-link (paranoid guard)
                saved_ev.event_id = event.pk
                saved_ev.volunteer_id = user.pk
                saved_ev.pk = ev_signup.pk  # ensure PK stays same
                saved_ev.save()
            return redirect(reverse("event_detail", kwargs={"pk": event_pk}))
    else:
        ev_form = EventPrepForm(instance=ev_signup, prefix="ev")
        user_form = UserPrepForm(instance=user, prefix="user")

    # ---- Age flags as of event date ----
    event_day = _as_date(event.event_date)
    is_16_plus = _age_at_least(user.date_of_birth, 16, event_day)  # True/False/None
    is_18_plus = _age_at_least(user.date_of_birth, 18, event_day)  # True/False/None

    # Under = NOT over (None propagates to None)
    under_16 = None if is_16_plus is None else (not is_16_plus)
    under_18 = None if is_18_plus is None else (not is_18_plus)

    # Colors: yellow if under_18 True or Unknown; red if under_16 True
    highlight_under_18 = (under_18 is True) or (under_18 is None)
    highlight_under_16 = (under_16 is True)



    return render(
        request,
        "haunt_ops/event_prep.html",
        {
            "event": event,
            "user": user,
            "ev_signup": ev_signup,
            "ev_form": ev_form,
            "user_form": user_form,
            "under_16": under_16,
            "under_18": under_18,
            "highlight_under_16": highlight_under_16,
            "highlight_under_18": highlight_under_18,
        },
    )


def user_group_memberships_view(request, pk):
    user = get_object_or_404(AppUser, pk=pk)
    memberships = GroupVolunteers.objects.filter(volunteer=user).select_related("group")
    return render(request, "haunt_ops/user_group_memberships.html", {
        "user": user,
        "memberships": memberships,
    })

def user_event_participation_view(request, pk):
    user_obj = get_object_or_404(AppUser, pk=pk)
    participations = EventVolunteers.objects.filter(volunteer=user_obj).select_related("event")
    return render(request, "haunt_ops/user_event_participation.html", {
        "user_obj": user_obj,            # avoid clobbering request.user context
        "participations": participations,
    })

def group_volunteers_view(request, pk):
    group = get_object_or_404(Groups, pk=pk)
    volunteers_qs = (
        GroupVolunteers.objects
        .filter(group=group)
        .select_related("volunteer")  # adjust FK name if needed
        .order_by("volunteer__last_name", "volunteer__first_name")
    )
    paginator = Paginator(volunteers_qs, 25)
    page_number = request.GET.get("page")
    volunteers_page = paginator.get_page(page_number)
    return render(request, "haunt_ops/group_volunteers.html", {
        "group": group,
        "volunteers_page": volunteers_page,
    })

def ticket_sales_list(request):
    """
    Paginated listing of Events that have TicketSales.
    Each row is an Event annotated with totals from its TicketSales rows.
    Links to /events/<event_id>/ (event_detail.html).
    """
    qs = (
        Events.objects
        .filter(ticketsales__isnull=False)
        .annotate(
            total_shows=Count("ticketsales", distinct=True),
            total_purchased=Sum("ticketsales__tickets_purchased"),
            total_remaining=Sum("ticketsales__tickets_remaining"),
            first_start_time=Min("ticketsales__event_start_time"),
            last_end_time=Max("ticketsales__event_end_time"),
        )
        .order_by("first_start_time", "event_name")
    )

    # Total across ALL TicketSales rows (not just current page)
    total_tickets_sold = TicketSales.objects.aggregate(
        total=Coalesce(Sum("tickets_purchased"), 0)
    )["total"]

    paginator = Paginator(qs, 25)  # 25 events per page
    page = request.GET.get("page", 1)
    try:
        events_page = paginator.page(page)
    except PageNotAnInteger:
        events_page = paginator.page(1)
    except EmptyPage:
        events_page = paginator.page(paginator.num_pages)

    return render(request, "haunt_ops/ticket_sales_list.html", {
        "events_page": events_page,
        "total_tickets_sold": total_tickets_sold,
    })

def ticket_sales_detail(request, event_pk):
    """
    Show all TicketSales rows for a single Event, including start/end times,
    tickets sold/remaining, and link to the event_detail page.
    """
    event = get_object_or_404(Events, pk=event_pk)

    rows = (
        TicketSales.objects
        .filter(event_id=event)
        .select_related("event_id")
        .order_by("event_start_time", "id")
    )

    totals = rows.aggregate(
        total_purchased=Sum("tickets_purchased"),
        total_remaining=Sum("tickets_remaining"),
    )

    return render(
        request,
        "haunt_ops/ticket_sales_detail.html",
        {
            "event": event,
            "rows": rows,
            "totals": totals,
        },
    )


@login_required
def logout_view(request):
    """
    Log the user out and redirect to the login page.
    """
    logout(request)
    return redirect('login')   # or wherever you want them to go
