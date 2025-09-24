"""
This file contains URL patterns for the HauntOps application.
It maps URLs to views for user profiles, signup, and the home page.
"""
from django.urls import path, reverse_lazy, include
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeView,
    PasswordChangeDoneView,
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView,
)
from .forms import StyledPasswordResetForm, StyledSetPasswordForm, StyledPasswordChangeForm
from haunt_ops.views import public_profile
from . import views

urlpatterns = [
    # Core pages
    path("", views.home, name="home"),
    path("profile/", views.profile_view, name="profile"),
    path("profile/<str:username>/", public_profile, name="public_profile"),
    path("signup/", views.signup, name="signup"),

    # Users
    path("users/", views.user_list, name="user_list"),
    path("users/<int:pk>/", views.user_detail, name="user_detail"),
    path("users/<int:pk>/groups/", views.user_group_memberships_view, name="user_group_memberships"),
    path("users/<int:pk>/events/", views.user_event_participation_view, name="user_event_participation"),

    # Events
    path("events/", views.events_list, name="events_list"),
    path("events/<int:pk>/", views.event_detail, name="event_detail"),
    path(
        "events/<int:event_pk>/volunteer/<int:vol_pk>/prep/quick/",
        views.event_prep_quick_update,
        name="event_prep_quick_update",
    ),
    path("events/<int:event_pk>/volunteer/<int:vol_pk>/prep/", views.event_prep_view, name="event_prep"),
    path("events/volunteers/", views.event_volunteers_list, name="event_volunteers_list"),

    # Ticket Sales
    path("ticket-sales/", views.ticket_sales_list, name="ticket_sales_list"),
    path("ticket-sales/<int:event_pk>/",views.ticket_sales_detail, name="ticket_sales_detail"),

    # Groups
    path("groups/", views.groups_list, name="groups_list"),
    path("groups/<int:pk>/volunteers/", views.group_volunteers_view, name="group_volunteers"),
    path("group-volunteers/", views.group_volunteers_list, name="group_volunteers_list"),

    # Auth (site)
    path(
        "accounts/login/",
        LoginView.as_view(
            template_name="registration/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("accounts/logout/", LogoutView.as_view(next_page="login"), name="logout"),

    # Password CHANGE (logged-in users)
    path(
        "accounts/password_change/",
        PasswordChangeView.as_view(
            template_name="registration/password_change_form.html",
            success_url=reverse_lazy("password_change_done"),
            form_class=StyledPasswordChangeForm,
        ),
        name="password_change",
    ),
    path(
        "accounts/password_change/done/",
        PasswordChangeDoneView.as_view(
            template_name="registration/password_change_done.html",
        ),
        name="password_change_done",
    ),

    # Password RESET (email flow)
    path(
        "password-reset/",
        PasswordResetView.as_view(
            template_name="registration/password_reset_form.html",
            email_template_name="registration/password_reset_email.html",
            subject_template_name="registration/password_reset_subject.txt",
            form_class=StyledPasswordResetForm,
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html",
            form_class=StyledSetPasswordForm,
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
]

path("api/", include("haunt_ops.api_urls"))
