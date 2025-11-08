# ✅ GOOD: No self-include

from django.urls import path
from . import views

urlpatterns = [
    path('', views.folder_list, name='folder_list'),
    path('browse/<path:subpath>/', views.browse_folder, name='browse_folder'),
]

