from __future__ import annotations
import json
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from .core import IgiturError, IgiturAuthenticationError

class GaudeamSession():
    """Session information to talk to Gaudeam. 
    """

    def __init__(self, gaudeam_session_cookie: str, subdomain: str):
        """Creates a session for Gaudeam

        Args:
            gaudeam_session_cookie (str): The cookie value from "_gaudeam_session" 
                                    exported from a logged in browser session
            subdomain (str): Subdomain of your gaudeam instance, 
                                    e.g. "yourinstance" for "yourinstance.gaudeam.de"
        """
        self._gaudeam_session = gaudeam_session_cookie
        self._subdomain = subdomain

        self._client = requests.Session()
        self._client.cookies.update({"_gaudeam_session": gaudeam_session_cookie})

    @staticmethod
    def with_user_auth(email: str, password: str) -> GaudeamSession:
        """Logs in using user and password and creates a session. 

        Args:
            email (str): Email of your user account
            password (str): Password of your user account

        Raises:
            IgiturAuthenticationError: If user and/or password are wrong

        Returns:
            GaudeamSession: The session to Gaudeam
        """
        temp_session = requests.Session()
        url_login = "https://auth.gaudeam.de/login"
        response_login_page = temp_session.get(url_login)
        soup = BeautifulSoup(response_login_page.content, "html.parser")
        authenticity_token = soup.find("input", {"name": "authenticity_token"})["value"]
        data = {
            "authenticity_token": authenticity_token,
            "user[email]": email,
            "user[password]": password,
            "user[remember_me]": [
                "0",
                "1"
            ],
            "user[anchor_after_login]": "",
            "commit": "Einloggen"
        }

        response_auth = temp_session.post(url_login, data, allow_redirects=False)
        status = response_auth.status_code
        if status == 302: # redirect, login successful
            redirect_url = response_auth.headers.get("Location")
            subdomain = redirect_url.removeprefix("https://").split(".gaudeam.de")[0]
            session_cookie = response_auth.cookies["_gaudeam_session"]

            return GaudeamSession(session_cookie, subdomain)
        else:
            raise IgiturAuthenticationError("Failed to login to gaudeam, check credentials")


    def client(self) -> requests.Session:
        """Returns the requests session for the gaudeam connection

        Returns:
            requests.Session: session for gaudeam connection
        """
        return self._client

    def url(self) -> str:
        """Returns the base url, e.g. "https://yourinstance.gaudeam.de"

        Returns:
            str: the base url of your instance
        """
        return f"https://{self._subdomain}.gaudeam.de"

    def save_to_file(self, file_path: Path|str) -> None:
        """Saves the session to a local file

        Args:
            file_path (Path | str): Path to the file to save the session to
        """
        file_path = Path(file_path)
        with open(file_path, "w") as f:
            json.dump({
                "gaudeam_session_cookie": self._gaudeam_session,
                "subdomain": self._subdomain
            }, f)

    @staticmethod
    def from_file(file_path: Path|str) -> GaudeamSession:
        """Loads a gaudeam session from a local file

        Args:
            file_path (Path | str): Path to the file to load the session from
        Returns:
            GaudeamSession: The loaded session
        """
        file_path = Path(file_path)
        with open(file_path, "r") as f:
            data = json.load(f)
            session = GaudeamSession(
                gaudeam_session_cookie=data["gaudeam_session_cookie"],
                subdomain=data["subdomain"]
            )
        if session.is_valid():
            return session
        else:
            raise IgiturAuthenticationError("Loaded session is not valid anymore, Please log in again.")

    def is_valid(self) -> bool:
        """Checks if the session is still valid by making a test request

        Returns:
            bool: True if the session is valid
        """
        url = f"{self.url()}/api/v1/current_member"
        response = self.client().get(url)
        return response.status_code == 200

    def get_user_email(self) -> str:
        """Gets the email of the logged in user

        Returns:
            str: Email of the logged in user
        """
        url = f"{self.url()}/api/v1/current_member"
        response = self.client().get(url)
        data = response.json()
        return data["personal_record"]["email"]
