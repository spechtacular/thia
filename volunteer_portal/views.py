
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None and not user.is_staff:  # block staff from logging in here
            login(request, user)
            return redirect('volunteer_home')
        return render(request, 'volunteer_portal/login.html', {'error': 'Invalid credentials'})
    return render(request, 'volunteer_portal/login.html')

@login_required
def home(request):
    return render(request, 'volunteer_portal/home.html', {'user': request.user})

def logout_view(request):
    logout(request)
    return redirect('volunteer_login')
