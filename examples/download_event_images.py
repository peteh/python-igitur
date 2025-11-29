import logging
from pathlib import Path
from datetime import datetime, timedelta
from igitur import GaudeamSession, GaudeamCalendar
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

session = GaudeamSession.with_user_auth("your@email.de", "yourpassword")

calendar = GaudeamCalendar(session)

# Get a time range from now to 14 days ago
today = datetime.now()
past = today - timedelta(days=14)

# get all events in the time frame
events = calendar.global_calendar(past, today)

# download all media files for each event into a folder named with the event date and title with subfolders for each uploader
base_path = Path("./downloaded_events/")
for event in events:
    date_str = event.get_start_datetime().strftime("%Y-%m-%d")
    folder_name = f"{date_str} {event.get_title()}"
    logging.info(f"Downloading media for event '{event.get_title()}' into folder '{folder_name}'")
    event_path = base_path / folder_name
    event.download_media(event_path)
