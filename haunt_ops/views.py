"""
This file contains views for the HauntOps application.
It includes views for user profiles, signup, and the home page.
"""
import logging
from django.contrib.auth import authenticate, login
from django.contrib.auth import get_user_model
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from .forms import PublicSignupForm, AppUserChangeForm, ProfileForm
from django.urls import reverse

from .forms import PublicSignupForm, ProfileForm, AppUserChangeForm
from .models import AppUser


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
    return render(request, 'haunt_ops/user_list.html', {'users': users})


def user_detail(request, pk):
    user = get_object_or_404(AppUser, pk=pk)
    return render(request, 'haunt_ops/user_detail.html', {'user': user})


@login_required
def logout_view(request):
    """
    Log the user out and redirect to the login page.
    """
    logout(request)
    return redirect('login')   # or wherever you want them to go
