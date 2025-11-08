import os
from django.conf import settings
from django.http import Http404
from django.shortcuts import render


def folder_list(request):
    base_path = settings.VIDEO_LIBRARY_ROOT

    ignore_list = {'__pycache__', '.DS_Store', '.git', '.svn'}
    folders = []

    for folder in os.listdir(base_path):
        full_path = os.path.join(base_path, folder)
        if not os.path.isdir(full_path):
            continue
        if folder in ignore_list or folder.startswith('.'):
            continue
        folders.append(folder)

    # ✅ Sort: numbers first, then alphabetically
    def sort_key(name):
        try:
            # Extract leading number if present
            prefix = name.split()[0]  # or name.split('-')[0] depending on your format
            return (0, int(prefix))
        except (ValueError, IndexError):
            return (1, name.lower())

    folders = sorted(folders, key=sort_key)

    return render(request, 'videos/folder_list.html', {'folders': folders})



def browse_folder(request, subpath):
    folder_path = os.path.join(settings.VIDEO_LIBRARY_ROOT, subpath)

    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        raise Http404("Folder does not exist")

    items = []
    for item in os.listdir(folder_path):
        full_path = os.path.join(folder_path, item)

        is_dir = os.path.isdir(full_path)
        is_video = item.lower().endswith('.mp4')
        is_image = item.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))

        items.append({
            'name': item,
            'is_dir': is_dir,
            'relative_path': os.path.join(subpath, item).replace("\\", "/"),
            'is_video': is_video,
            'is_image': is_image,
        })

    return render(request, 'videos/browse_folder.html', {
        'items': items,
        'current_path': subpath,
        'video_base_url': settings.VIDEO_LIBRARY_URL,
    })
