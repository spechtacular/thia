from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import authenticate, login
from django.urls import reverse_lazy, reverse
from django.views.generic import CreateView
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .forms import PublicSignupForm, AppUserChangeForm

def signup(request):
   if request.method == 'POST':
       form = PublicSignupForm(request.POST)
       if form.is_valid():
           form.save()
           return redirect('login')  # redirect after signup
   else:
      form = PublicSignupForm()
   return render(request, 'registration/signup.html', {'form': form})


def home(request):
    return render(request, 'home.html')


@login_required
def profile_view(request):
    if request.method == 'POST':
        form = AppUserChangeForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('profile')  # stay on the same page after saving
    else:
        form = AppUserChangeForm(instance=request.user)

    return render(request, 'profile.html', {'form': form})


def login_view(request):
    if request.method == "POST":
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
    user = get_object_or_404(User, username=username)
    profile = user.profile
    return render(request, 'public_profile.html', 
       {'user_profile': profile})

