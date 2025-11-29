import argcomplete
import argparse
import logging
from datetime import datetime, timedelta
from getpass import getpass
from igitur import GaudeamSession
from pathlib import Path
import sys
logging.basicConfig(level=logging.INFO)
from .core import IgiturError
from .drive import GaudeamDriveFolder, GaudeamResizedImageUploader
from .calendar import GaudeamEvent, GaudeamCalendar

SESSION_PATH = Path.home() / ".igitur_session"

def login(email: str, password: str) -> GaudeamSession:

    session = GaudeamSession.with_user_auth(email, password)

    # save to home directory
    file_path = Path("~/.igitur_session").expanduser()
    session.save_to_file(file_path)
    print(f"Logged in, Session saved to {file_path}")
    return 0

def logout():
    if SESSION_PATH.exists():
        SESSION_PATH.unlink()
        print("Logged out and session file deleted.")
    else:
        print("No session file found.")
    return 0

def status():
    if not SESSION_PATH.exists():
        raise IgiturError("No session found. Please login first.")
    session = GaudeamSession.from_file(SESSION_PATH)
    if not session.is_valid():
        raise IgiturError("Session is invalid. Please login again.")
    print(f"Logged in as {session.get_user_email()} at {session.url()}")

def ensure_logged_in() -> GaudeamSession:
    if not SESSION_PATH.exists():
        raise IgiturError("No session found. Please login first.")
    session = GaudeamSession.from_file(SESSION_PATH)
    if not session.is_valid():
        raise IgiturError("Session is invalid. Please login again.")
    return session

def download(folder_id: str, destination: Path):
    session = ensure_logged_in()
    folder = GaudeamDriveFolder(session, folder_id)
    folder.download(destination)
    return 0

def download_event_media(event_id: str, destination: Path):
    session = ensure_logged_in()
    event = GaudeamEvent(session, event_id)
    event.download_media(destination)
    return 0

def download_event_media_days(days: int,  destination: Path):
    session = ensure_logged_in()
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
        event_path = base_path / folder_name
        event.download_media(event_path)


def upload(folder_id: str, source: Path):
    session = ensure_logged_in()
    folder = GaudeamDriveFolder(session, folder_id)
    if source.exists() is False:
        raise IgiturError(f"Source path '{source}' does not exist.")

    if source.is_file():
        folder.upload_file(source)
    elif source.is_dir():
        folder.upload_folder(source)
    return 0

def upload_compressed_images(session: GaudeamSession, folder_id: str, source: Path):
    if source.exists() is False or source.is_dir() is False:
        raise IgiturError(f"Source path '{source}' does not exist or is not a directory.")

    folder = GaudeamDriveFolder(session, folder_id)
    uploader = GaudeamResizedImageUploader()
    uploader.upload_folder_resized(source, folder)
    return 0

def main():
    parser = argparse.ArgumentParser(
        prog="igitur",
        description="Command line interface to interact with Gaudeam."
    )
    subparsers = parser.add_subparsers(dest="command", required = True)

    # login comma
    login_parser = subparsers.add_parser(
        "login",
        help="Login to Gaudeam with email and password."
    )
    login_parser.add_argument("-u", "--email", help="Email address of the user.")
    login_parser.add_argument("-p", "--password", help="Password of the user.")
    
    status_parser = subparsers.add_parser("status", help="Check login status.")
    
    logout_parser = subparsers.add_parser("logout", help="Logout and delete session.")
    
    help_parser = subparsers.add_parser("help", help="Show help message.")
    
    download_parser = subparsers.add_parser("download", help="Download files from a Gaudeam folder.")
    download_parser.add_argument("folder_id", help="ID of the Gaudeam folder to download from.")
    download_parser.add_argument("destination", help="Destination directory to save files.", default=".")
    
    download_event_media_parser = subparsers.add_parser("download-event-media", help="Download all media files from a Gaudeam event.")
    download_event_media_parser.add_argument("event_id", help="ID of the Gaudeam event to download media from.")
    download_event_media_parser.add_argument("destination", help="Destination directory to save files.", default=".")
    
    download_event_media_days_parser = subparsers.add_parser("download-event-media-days", help="Download all media files from Gaudeam events in the last N days.")
    download_event_media_days_parser.add_argument("days", type=int, help="Number of days to look back for events.", default=14)
    download_event_media_days_parser.add_argument("destination", help="Destination directory to save files.", default=".")
    
    upload_parser = subparsers.add_parser("upload", help="Upload files or the content of a folder to a Gaudeam folder.")
    upload_parser.add_argument("folder_id", help="ID of the Gaudeam folder to upload to.")
    upload_parser.add_argument("source", help="Path to the file or folder to upload.")

    upload_image_parser = subparsers.add_parser("upload-images", help="Upload a folder and compress all images before uploading to a Gaudeam folder.")
    upload_image_parser.add_argument("folder_id", help="ID of the Gaudeam folder to upload to.")
    upload_image_parser.add_argument("source", help="Path to the folder containing images to upload.")

    # Enable tab completion
    argcomplete.autocomplete(parser)

    args = parser.parse_args()

    try:
        if args.command == "login":
            email = args.email or input("Email: ")
            password = args.password or getpass("Password: ")
            login(email, password)

        elif args.command == "logout":
            logout()

        elif args.command == "status":
            status()

        elif args.command == "download":
            download(args.folder_id, Path(args.destination))
        
        elif args.command == "download-event-media":
            download_event_media(args.event_id, Path(args.destination))

        elif args.command == "download-event-media-days":
            download_event_media_days(args.days, Path(args.destination))

        elif args.command == "upload":
            upload(args.folder_id, Path(args.source))
        
        elif args.command == "upload-images":
            session = ensure_logged_in()
            upload_compressed_images(session, args.folder_id, Path(args.source))

        elif args.command is None or args.command == "help":
            parser.print_help()
            sys.exit(1)
    except IgiturError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    sys.exit(0) # successful exit