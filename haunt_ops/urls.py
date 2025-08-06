"""
This file contains URL patterns for the HauntOps application.
It maps URLs to views for user profiles, signup, and the home page.
"""
from django.urls import path
from django.contrib.auth.views import LogoutView

from haunt_ops.views import public_profile, LogoutViaGetView
from . import views

urlpatterns = [
    path('profile/', views.profile_view, name='profile'),
    path('signup/', views.signup, name="signup"),
    path('profile/<str:username>/', public_profile, name='public_profile'),
    path('', views.home, name='home'),
    path('users/', views.user_list, name='user_list'),
    path('users/<int:pk>/', views.user_detail, name='user_detail'),
    path('events/<int:pk>/', views.event_detail, name='event_detail'),
    path('accounts/logout/',LogoutView.as_view(next_page='login'), name='logout'),
    path('events/', views.events_list, name='events_list'),
    path('event-volunteers/', views.event_volunteers_list, name='event_volunteers_list'),
    path('groups/', views.groups_list, name='groups_list'),
    path('group-volunteers/', views.group_volunteers_list, name='group_volunteers_list'),
    path('accounts/logout/', LogoutViaGetView.as_view(), name='logout'),
]
