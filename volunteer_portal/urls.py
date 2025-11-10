# volunteer_portal/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='volunteer_home'),
    path('login/', views.login_view, name='volunteer_login'),
    path('logout/', views.logout_view, name='volunteer_logout'),
]
