#!/bin/bash
# rename profile image files to match the names in the volunteer database, label the image with the volunteers name and overwrite the original image 
# --commit option makes the changes, if it is omitted nothing is updated
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <path_to_image_directory> "
    exit 1
fi
python manage.py rename_images_to_db_names "$1" --alias-csv image_aliases.csv --commit  --label --label-overwrite --update-image-url
