"""
This file contains views for the HauntOps application.
It includes views for user profiles, signup, and the home page.
"""
from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .forms import PublicSignupForm, AppUserChangeForm

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
    if request.method == "POST" and 'username' in request.POST and 'password' in request.POST:
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect(reverse('public_profile', args=[user.username]))
        else:
            return render(request, 'login.html', {'error': 'Invalid credentials'})
    return render(request, 'login.html')


def public_profile(request, username):
    """
    View for displaying a public profile of a user.
    It retrieves the user by username and renders the public profile template.
    If the user does not exist, it raises a 404 error.
    """
    user = get_object_or_404(User, username=username)
    profile = user.profile
    return render(request, 'public_profile.html', 
       {'user_profile': profile})

