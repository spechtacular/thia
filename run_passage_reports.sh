python manage.py passage_reports \
  --email="$GOPASSAGE_EMAIL" \
  --password="$GOPASSAGE_PASSWORD" \
  --base-url 'https://app.gopassage.com/users/sign_in' \
  --scrape-upcoming \
  --output-csv "./upcoming_events.csv" \
  --no-headless
