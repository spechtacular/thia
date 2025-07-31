"""
This file contains URL patterns for the HauntOps application.
It maps URLs to views for user profiles, signup, and the home page.
"""
from django.urls import path
from haunt_ops.views import public_profile
from . import views

urlpatterns = [
    path('profile/', views.profile_view, name='profile'),
    path('signup/', views.signup, name="signup"),
    path('profile/<str:username>/', public_profile, name='public_profile'), #new
    path('', views.home, name='home'),
]

