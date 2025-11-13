from django.urls import path
from . import views

urlpatterns = [
    path('', views.folder_list, name='folder_list'),
    path('<path:folder_path>/', views.browse_folder, name='browse_folder'),
]
