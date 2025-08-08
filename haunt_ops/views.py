"""
This file contains views for the HauntOps application.
It includes views for user profiles, signup, and the home page.
"""
import logging
from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import login_required
from django.db.models.functions import Lower
from django.contrib.auth import logout


from .forms import PublicSignupForm, AppUserChangeForm, ProfileForm, EventPrepForm

from .models import AppUser, Events, Groups, EventVolunteers, GroupVolunteers


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

def profile_view(request):
    """
    user profile page
    """
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('profile')
    else:
        form = ProfileForm(instance=request.user)

    return render(request, 'profile.html', {'form': form})

def user_list(request):
    """
    list users from app_user table
    """
    users = AppUser.objects.all()
    # Paginate with 20 users per page
    paginator = Paginator(users, 20)
    page = request.GET.get('page', 1)

    try:
        users_page = paginator.page(page)
    except PageNotAnInteger:
        users_page = paginator.page(1)
    except EmptyPage:
        users_page = paginator.page(paginator.num_pages)

    return render(request, 'haunt_ops/user_list.html', {
        'users_page': users_page
    })

def event_volunteers_list(request):
    evols = EventVolunteers.objects.all().order_by('date')
    # Paginate with 20 event volunteers per page
    paginator = Paginator(evols, 20)
    page = request.GET.get('page', 1)

    # DEBUGGING: log out how many records you found
    logging.getLogger(__name__).info("Found %d event volunteers", evols.count())
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
    paginator = Paginator(events, 20)
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
    groups = Groups.objects.all()
    # Paginate with 10 groups per page
    paginator = Paginator(groups, 20)
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
    user = get_object_or_404(AppUser, pk=pk)
    return render(request, 'haunt_ops/user_detail.html', {'user': user})

def event_detail(request, pk):
    """
    page that lists all volunteers for a specific event
    """
    # Grab the event or 404
    event = get_object_or_404(Events, pk=pk)

    # All volunteers for this event:
     # Order by volunteer last name (case-insensitive), then first name
    signups = (
        EventVolunteers.objects
        .filter(event=event)
        .select_related('volunteer')  # joins AppUser for efficiency
        #.annotate(last_lower=Lower('volunteer__last_name'))
        #.order_by('last_lower')
        .order_by('volunteer__last_name', 'volunteer__first_name')
    )

    return render(request, 'haunt_ops/event_detail.html', {
        'event': event,
        'signups': signups,
    })

def event_prep(request, event_pk, vol_pk):
    """
    Page related to each volunteers prep for a specific event
    """
    event  = get_object_or_404(Events, pk=event_pk)
    ev_signup = get_object_or_404(
        EventVolunteers.objects.select_related('volunteer','event'),
        pk=vol_pk, event_id=event_pk
    )

    if request.method == 'POST':
        form = EventPrepForm(request.POST, instance=ev_signup)
        if form.is_valid():
            form.save()
            return redirect('event_detail', pk=event_pk)
    else:
        form = EventPrepForm(instance=ev_signup)

    return render(request, 'event_prep.html', {
        'event':  event,
        'ev_signup': ev_signup,
        'user':   ev_signup.volunteer,
        'form':   form,
    })


@login_required
def logout_view(request):
    """
    Log the user out and redirect to the login page.
    """
    logout(request)
    return redirect('login')   # or wherever you want them to go
