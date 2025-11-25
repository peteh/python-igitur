import argcomplete
import argparse
import logging
from getpass import getpass
from igitur import GaudeamSession
from pathlib import Path
import sys
logging.basicConfig(level=logging.INFO)
from .core import IgiturError
from .drive import GaudeamDriveFolder

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

def main():
    parser = argparse.ArgumentParser(
        prog="igitur",
        description="Command line interface to interact with Gaudeam."
    )
    subparsers = parser.add_subparsers(dest="command", required = True)

    # login command
    login_parser = subparsers.add_parser(
        "login",
        help="Login to Gaudeam with email and password."
    )
    login_parser.add_argument("-u", "--email", help="Email address of the user.")
    login_parser.add_argument("-p", "--password", help="Password of the user.")
    
    status_parser = subparsers.add_parser("status", help="Check login status.")
    
    logout_parser = subparsers.add_parser("logout", help="Logout and delete session.")
    
    download_parser = subparsers.add_parser("download-folder", help="Download files from a Gaudeam folder.")
    download_parser.add_argument("folder_id", help="ID of the Gaudeam folder to download from.")
    download_parser.add_argument("-d", "--destination", help="Destination directory to save files.", default=".")

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
        
        elif args.command == "download-folder":
            session = ensure_logged_in()
            folder = GaudeamDriveFolder(session, args.folder_id)
            destination_path = Path(args.destination)
            folder.download(destination_path)
    except IgiturError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    sys.exit(0) # successful exit