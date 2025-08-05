- Secret project values are stored in a **.env** file in the project root directory, this file is not in the repo for security reasons.
- **requirements.txt** : file contains the pip modules to be installed for the Django  project.
- **setup_venv.py** : script will create a local file named **.venv** in the project root directory to be used for a local development environment.
- This is the sequence of events used to clear and reload the local Django postgresql database.
   1. **clear_haunt_data.py** clears all project tables except for admin and test accounts, there is a --dry-run option to run the script without deleting any project data from postgresql.
      1. python manage.py clear_haunt_data 
   2. After clearing the project database the local Django project postgresql database tables must be restored from the iVolunteer database. Here are the steps:
      1. **bulk_load_groups_from_config.py** : this loads group labels from a project config file instead of scraping the iVolunteer web page. There are options to use a custom configuration file and a dry-run.
         1. python manage.py load_groups_from_config
      2. **run_selenium_events_query.py** : scrapes all iVolunteer event labels and stores them in the postgresql events table.
         1. python manage.py run_selenium_events_query --config=config/selenium_config.yaml
      3. **run_selenium_users_query.py** : runs the iVolunteer DB users XLS formatted report.
         1. python manage.py run_selenium_users_query
      4. **bulk_load_users_from_ivolunteers.py** : inserts report data from the converted csv file into the postgresql app_user table.
         1. python manage.py load_users_from_csv --csv path/to/users.csv
      5. **update_user_profile_pic.py** : matches volunteer images to database users and create the users profile image url. This script only processes one user at a time, it is faster to create a bash script using this Django script to load multiple image links. 
         1. All of the user image files must follow these requirements:
            1. The image file name should be in the following format "first_last_pic.ext"
            2. There must be an underscore between the first and last name. 
            3. there must be an underscore after the last name before the word pic.
            4. The first name and last name must match the names used in the database, some people give formal first names etc.
            5. The file extension must be png, jpg, or jpeg.
         2. The script to label the user images is in the utils folder:
            1. **label_people_pics.py** adds the name used int he image file name to the actual image.
      6. **run_selenium_participation_query.py** : runs the event participation iVoulnteer database report.
         1. python manage.py run_selenium_participation_query
      7. **bulk_load_events_from_ivolunteer.py** : inserts new report data from the converted csv report file into the postgresql event_volunteers table.
         1. python manage.py bulk_load_events_from_ivolunteer --csv path/to/users.csv
- This is the sequence used to update the existing Django postgresql database contents. 
   1. **run_selenium_users_query.py** : runs the iVolunteer DB users XLS formatted report.
      1. python manage.py run_selenium_users_query
   2. **bulk_load_users_from_ivolunteers.py** : inserts or updates new report data from the converted csv file into the postgresql app_user table.
      1. python manage.py load_users_from_csv --csv path/to/users.csv
   3.  **update_user_profile_pic.py** : matches volunteer images to database users and create the users profile image url. This script only processes one user at a time, it is faster to create a bash script using this Django script to load multiple image links. 
         1. All of the user image files must follow these requirements:
            1. The image file name should be in the following format "first_last_pic.ext"
            2. There must be an underscore between the first and last name. 
            3. there must be an underscore after the last name before the word pic.
            4. The first name and last name must match the names used in the database, some people give formal first names etc.
            5. The file extension must be png, jpg, or jpeg.
         2. The script to label the user images is in the utils folder:
            1. **label_people_pics.py** adds the name used int he image file name to the actual image.
   4. **run_selenium_participation_query.py** : runs the event participation iVoulnteer database report.
      1. python manage.py run_selenium_participation_query
   5. **bulk_load_events_from_ivolunteer.py** : inserts or updates new report data from the converted csv report file into the postgresql event_volunteers table.
      1. python manage.py bulk_load_events_from_ivolunteer --csv_file=path/to/users.csv

