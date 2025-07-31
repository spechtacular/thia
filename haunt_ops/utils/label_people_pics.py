"""
This script iterates through all files in a specified directory, processes image files by adding the filename as a title to the image, 
and saves the modified images with a new name. 
It uses the Pillow library for image processing.

"""
import os
import argparse
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError, ImageOps



def iterate_files(directory):
    """
    Iterates through all files in a given directory.

    Args:
        directory: The path to the directory.
    """
    try:
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            if os.path.isfile(filepath):
                # Process the file
                print(f"File: {filepath}")
                add_filename_title(filepath)
            elif os.path.isdir(filepath):
              # Optionally process subdirectories
              print(f"Directory: {filepath}")
              iterate_files(filepath) # Recursive call to handle nested directories
    except FileNotFoundError:
      print(f"Error: Directory not found: {directory}")
    except Exception as e:
      print(f"An error occurred: {e}")



def add_filename_title(image_path, font_size=25, font_color=(255, 255, 255), title_position=(5, 5)):
    """
    Adds the filename as a title to an image.

    Args:
        image_path (str): The path to the image file.
        font_size (int, optional): The font size of the title. Defaults to 20.
        font_color (tuple, optional): The color of the title text (RGB). Defaults to (255, 255, 255) - white.
        title_position (tuple, optional): The (x, y) coordinates of the title's top-left corner. Defaults to (10, 10).
    """
    print(f"file name: {image_path}")
    try:
        with Image.open(image_path) as img:
            # normalize image to prevent rotation of image
            img = ImageOps.exif_transpose(img)
            print(f"Image format: {img.format}")
            width,height = img.size
            draw = ImageDraw.Draw(img)
            print("image drawn")  
            # split filename and path
            filepath, filename = os.path.split(image_path)
            print(f"modifying file {filename}")
            # split name and extension
            basename, extension = os.path.splitext(filename)
            print(f"extension {extension}")
            namefield = basename.split("_")
            print(f"namefield {namefield}")
            # remove spaces around name
            staffname = namefield[0].strip() + " " + namefield[1].strip()
        
            print(f"fn={filename} , {staffname}")

            font_size = int(height * 0.1)  # 10% of image height

            print("font_size={font_size}")


            try:
                font = ImageFont.truetype("/System/Library/Fonts/Monaco.ttf", font_size)  # Requires the font file in the same directory, or specify full path
            except IOError as ioe:
                font = ImageFont.load_default(font_size)
                print(f"An IO error occurred: {ioe}, using the defaut font")


            new_image_path = filepath +"/" + basename + ".png" 
       
            # hard coded for my vampire pic, position was 180,150 
            draw.text((80,50), staffname, font=font, fill=font_color)
            img.save(new_image_path ) # Save with a new name to avoid overwriting
            print(f"Image saved with title: {new_image_path}")

    except FileNotFoundError:
        print(f"Error: Image file not found at {image_path}")
    except UnidentifiedImageError as e:
         print(f"could not determine image format {e}")



# parse command line arguments
parser = argparse.ArgumentParser("label_people_pics")
parser.add_argument("-d", "--dir", help="input image directory path", type=str, required=True)
args = parser.parse_args()


print(f"image folder {args.dir} specified:")
iterate_files(args.dir)



