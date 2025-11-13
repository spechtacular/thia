import os
from django.conf import settings
from django.shortcuts import render

VIDEO_ROOT = os.path.join(settings.MEDIA_ROOT, 'videos')


def folder_list(request):
    folders = [
        name for name in os.listdir(VIDEO_ROOT)
        if os.path.isdir(os.path.join(VIDEO_ROOT, name))
    ]
 
    print("Folders:", folders)
    return render(request, 'videos/folder_list.html', {'folders': folders})

def browse_folder(request, folder_path):
    abs_path = os.path.join(VIDEO_ROOT, folder_path)
    items = []

    for name in os.listdir(abs_path):
        full_path = os.path.join(abs_path, name)
        rel_path = os.path.join(folder_path, name)
        items.append({
            'name': name,
            'relative_path': rel_path,
            'is_dir': os.path.isdir(full_path),
            'is_video': name.lower().endswith(('.mp4', '.mov', '.avi')),
            'is_image': name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')),
        })

    context = {
        "items": items,
        "current_path": folder_path,
        "video_base_url": settings.MEDIA_URL + "videos/",  # This is usually "/media/"
    }
    return render(request, "videos/browse_folder.html", context)
