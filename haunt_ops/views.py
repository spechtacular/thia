"""
This file contains views for the HauntOps application.
It includes views for user profiles, signup, and the home page.
"""
import logging
from django.contrib.auth import authenticate, login
from django.contrib.auth import get_user_model
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib.auth.views import LogoutView
from django.urls import reverse

from .forms import PublicSignupForm, AppUserChangeForm, ProfileForm

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
    user = get_object_or_404(User, username=username)
    return render(request, 'public_profile.html', {'user_profile': user_obj})

def profile_view(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('profile')
    else:
        form = ProfileForm(instance=request.user)

    return render(request, 'profile.html', {'form': form})

def user_list(request):
    users = AppUser.objects.all()
    # Paginate with 10 users per page
    paginator = Paginator(users, 10)
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
    evols = EventVolunteers.objects.all()
    # Paginate with 10 event volunteers per page
    paginator = Paginator(evols, 10)
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
    # 1. Grab every row in the junction table
    ev_rows = GroupVolunteers.objects.all()

    data = []
    for ev in ev_rows:
        # 2. From each EventVolunteers, pull the two IDs
        user_id  = ev.volunteer_id
        group_id = ev.group_id

        # 3. Look up each record by its PK
        user  = AppUser.objects.get(pk=user_id)
        group = Groups.objects.get(pk=group_id)

        # 4. Build a dict of exactly the fields you want
        data.append({
            'group_name':   group.group_name,
            'email':        user.email,
            'first_name':   user.first_name,
            'last_name':    user.last_name,
            'phone1':       user.phone1,
        })

    # 5. Pass that list into the template
    return render(request, 'haunt_ops/group_volunteers_list.html', {
        'rows': data
    })

def events_list(request):
    """
    View for listing all events.
    It retrieves all events from the database and paginates them.
    """
    events = Events.objects.all()
    # Paginate with 10 events per page
    paginator = Paginator(events, 10)
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
    paginator = Paginator(groups, 10)
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
    event = get_object_or_404(Events, pk=pk)
    return render(request, 'haunt_ops/event_detail.html', {'event': event})

class LogoutViaGetView(LogoutView):
    def get(self, request, *args, **kwargs):
        # treat GET the same as POST
        return super().post(request, *args, **kwargs)


@login_required
def logout_view(request):
    """
    Log the user out and redirect to the login page.
    """
    logout(request)
    return redirect('login')   # or wherever you want them to go
