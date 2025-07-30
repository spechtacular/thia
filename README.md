- Secret project values are stored in a .env file in the project root directory, this file is not in the repo for security reasons.
- requirements.txt : file contains the pip modules to be installed for the Django  project.
- setup_venv.py : script will create a local .venv in the project root directory to be used for a local development environment.
- This is the sequence of events used to clear and reload the local Django postgresql database.
   1. To clear the project related database tables:
      1. clear_haunt_data.py clears all project tables except for admin and test accounts, there is a --dry-run option to run the script without deleting any project data from postgresql.
   2. After clearing the project database the local Django project postgresql database tables must be restored from the iVolunteer database. Here are the steps:
      1. run_selenium_groups_query.py : scrapes all iVolunteer group labels and stores them in the postgresql groups table.
         1. load_groups_from_config.py : this loads group labels from a project config file instead of scraping the iVolunteer web page. Use this only if the project config file has the same contents as the ivolunteer web page.
      2. run_selenium_events_query.py : scrapes all iVolunteer event labels and stores them in the postgresql events table.
      3. run_selenium_users_query.py to retrieve the iVolunteer DB users XLS formatted report.
         1. convert_xls_report_to_csv.py :  converts iVolunteer xls report file to csv format.
         2. replace_column_names.py : converts iVoulnteer report column labels to postgresql column names.
         3. bulk_load_users_from_ivolunteers.py : inserts report data from the converted csv file into the postgresql app_user table.
         4. update_user_profile_pic.py : matches volunteer images to database users and create the users image url. This script only does one user at a time, it is faster to create a bash script using this Django script to load multiple image links. (We need all of the user images, the file name should be in the following format "first_name last_name_updated.ext, there is a space between first and last name, the extension can be png, jpg, or jpeg.)
      4. run_selenium_participation_query.py : retrieves all event participation data from the iVoulnteer database report.
         1. convert_xls_report_to_csv.py : converts the xls report file to csv format.
         2. replace_column_names.py : converts iVoulnteer report column labels to postgresql column names.
         3. bulk_load_events_from_ivolunteer.py : inserts new report data from the converted csv report file into the postgresql event_volunteers table.
- This is the sequence used to update the existing Django postgresql database contents. 
   1. run_selenium_users_query.py to retrieve the iVolunteer DB users XLS formatted report.
      1. convert_xls_report_to_csv.py :  converts iVolunteer xls report file to csv format.
      2. replace_column_names.py : converts iVoulnteer report column labels to postgresql column names.
      3. bulk_load_users_from_ivolunteers.py : inserts new report data and updates existing report data from the converted csv report file into the postgresql app_user table.
      4. update_user_profile_pic.py : matches volunteer images to database users and create the users image url. This script only does one user at a time, it is faster to create a bash script using this Django script to load multiple image links. (We need all of the user images, the file name should be in the following format "first_name last_name_updated.ext, there is a space between first and last name, the extension can be png, jpg, or jpeg.)
   2. run_selenium_participation_query.py : retrieves event participation XLS formatted report from the iVoulnteer database.
      1. convert_xls_report_to_csv.py : converts the xls report file to csv format.
      2. replace_column_names.py : converts iVoulnteer report column labels to postgresql column names.
      3. bulk_load_events_from_ivolunteer.py : inserts new report data and updates existing report data from the converted csv report file into the postgresql event_volunteers table.


   
