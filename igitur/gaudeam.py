from __future__ import annotations
import logging
import datetime
import typing
from pathlib import Path
from .session import GaudeamSession
    

class GaudeamMembers:
    """Member directory of the gaudeam instance. 
    """
    def __init__(self, gaudeam_session: GaudeamSession):
        self._session = gaudeam_session

    def get_members(self, include_dead=False, include_alliances=False, include_resigned=False, seach_term=""):
        offset = 0
        limit = 100
        params = {
            "q": seach_term,
            "offset": offset,
            "limit": limit,
            "order": "name",
            "asc": "true",
            "dead": str(include_dead).lower(),
            "alliances": str(include_alliances).lower(),
            "resigned": str(include_resigned).lower()
        }

        response_count = self._session.client().get(f"{self._session.url()}/api/v1/members/count", params=params)
        if response_count.status_code != 200: 
            raise RuntimeError(f"Error fetching members: {response_count.status_code}, {response_count.text}")
        num_records = response_count.json()["count"]

        response_members = self._session.client().get(f"{self._session.url()}/api/v1/members/index", params=params)
        if response_members.status_code != 200:
            raise RuntimeError(f"Error fetching members: {response_count.status_code}, {response_count.text}")
        members = response_members.json()["results"]
        while len(members) < num_records:
            offset += limit
            params["offset"] = offset
            response_members = self._session.client().get(f"{self._session.url()}/api/v1/members/index", params=params)
            members.extend(response_members.json()["results"])
        return members

class GaudeamCalendar:
    """Class to access global and user calendar from gaudeam.de"""

    def __init__(self, gaudeam_session: GaudeamSession):
        self._session = gaudeam_session

    @staticmethod
    def date_string_to_datetime(date: str) -> datetime.datetime:
        """Gives a date time object back for dates in the following formats: 
            2025-11-02T14:23:45.123456Z
            Sun, 02 Nov 2025 14:23:45 +0000
        Args:
            date (str): The date string

        Returns:
            datetime.datetime: The parsed datetime
        """
        if date[-1] == "Z":
            dt = datetime.datetime.strptime(date, "%Y-%m-%dT%H:%M:%S.%fZ")
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        else:
            dt = datetime.datetime.strptime(date, "%a, %d %b %Y %H:%M:%S %z")
        return dt.astimezone(datetime.timezone.utc)

    def user_calendar(self, start_date: datetime.date, end_date: datetime.date) -> list[dict]:
        """Returns the custom user calendar for the currently logged in user. 

        Args:
            start_date (datetime.date): The start time to collect entries
            end_date (datetime.date): The end time to collect entries

        Returns:
            list[dict]: The list of events in this time
        """
        start_str = start_date.strftime("%Y-%m-%dT00:00:00Z")
        end_str = end_date.strftime("%Y-%m-%dT00:00:00Z")
        url = f"{self._session.url()}/user_calendar.json?start={start_str}&end={end_str}&timeZone=UTC"
        response = self._session.client().get(url)
        if response.status_code == 200:
            events = response.json()
            events = sorted(events, key=lambda x: self.date_string_to_datetime(x["start"]))
            return events
        else:
            raise RuntimeError(f"Error fetching calendar: {response.status_code}, {response.text}")

    def global_calendar(self, start_date: datetime.date, end_date: datetime.date) -> list[GaudeamEvent]:
        """Returns events from the global calendar of the instance. 

        Args:
            start_date (datetime.date): The start time from which to collect events
            end_date (datetime.date): The end time till which to collect events

        Returns:
            list[dict]: List of events
        """
        start_str = start_date.strftime("%Y-%m-%dT00:00:00Z")
        end_str = end_date.strftime("%Y-%m-%dT00:00:00Z")
        url = f"{self._session.url()}/global_calendar.json?start={start_str}&end={end_str}&timeZone=UTC"
        response = self._session.client().get(url)
        if response.status_code != 200:
            raise RuntimeError(f"Error fetching calendar: {response.status_code}, {response.text}")

        all_events = response.json()
        events = []
        for event_data in all_events:
            if "personal_records" in event_data["url"]: # skip, it's a birthday
                continue
            else: # normal events
                event_id = event_data["id"]
                events.append(GaudeamEvent(self._session, event_id, event_data))
        events = sorted(events, key=lambda x: self.date_string_to_datetime(x._properties["start"]))

        return events

class GaudeamEvent():
    def __init__(self, session: GaudeamSession, event_id: str, properties: dict = None):
        self._session = session
        self._event_id = event_id
        if properties is None:
            self._properties = self._get_properties()
        else:
            self._properties = properties

    def _get_properties(self) -> dict:
        url = f"{self._session.url()}/api/v1/events/{self._event_id}"
        response = self._session.client().get(url)
        if response.status_code == 200:
            return response.json()
        else:
            raise RuntimeError(f"Error fetching event properties for event '{self._event_id}': {response.status_code}, {response.text}")

    def get_title(self) -> str:
        return self._properties["title"]

    def get_description(self) -> str:
        return self._properties["description"]
    
    def get_event_url(self) -> str:
        return self._properties["url"]
    
    def download_media(self, folder_path: Path|str):
        folder_path = Path(folder_path)
        for post in self.get_posts():
            creator_name = post.get_creator_name()

            for media in post.get_media():
                sub_folder = folder_path / creator_name
                if not sub_folder.exists():
                    sub_folder.mkdir(parents=True)
                file_name = media.get_download_name()

                save_path = sub_folder / file_name
                if save_path.exists():
                    logging.info(f"Skipping {save_path}: File already exists")
                    continue
                media.download(save_path)

    def get_start_datetime(self) -> datetime.datetime:
        return GaudeamCalendar.date_string_to_datetime(self._properties["start"])

    def get_posts(self) -> typing.List[EventPost]:
        url = f"{self._session.url()}/api/v1/events/{self._event_id}/posts"
        response = self._session.client().get(url)
        if response.status_code == 200:
            post_list = []
            for post_data in response.json():
                post_id = post_data["id"]
                post = EventPost(self._session, self._event_id, post_id, post_data)
                post_list.append(post)
            return post_list
        else:
            raise RuntimeError(f"Could not get posts for event_id '{self._event_id}'")

class EventPost():

    def __init__(self, session: GaudeamSession, event_id: str, post_id: str, properties = None):
        self._session = session
        self._event_id = event_id
        self._post_id = post_id
        if properties is None:
            self._properties = self._get_properties()
        else:
            self._properties = properties

    def _get_properties(self) -> dict:
        url = f"{self._session.url()}/api/v1/events/{self._event_id}/posts/{self._post_id}"
        response = self._session.client().get(url)
        if response.status_code == 200:
            return response.json()
        else:
            raise RuntimeError(f"Error fetching post properties for post '{self._post_id}': {response.status_code}, {response.text}")

    def get_creator_name(self) -> str:
        return self._properties["creator"]["full_name"]

    def get_media(self) -> GaudeamMedia:
        #/api/v1/posts/post_id/event_media
        url = f"{self._session.url()}/api/v1/posts/{self._post_id}/event_media"
        response = self._session.client().get(url)
        if response.status_code == 200:
            media_list = []
            for media_data in response.json():
                media_id = media_data["id"]
                media_list.append(GaudeamMedia(self._session, media_id, media_data))
            return media_list
        else:
            raise ValueError(f"Could not get media for post_id '{self._post_id}': {response.status_code}, {response.text}")

class GaudeamMedia():
    def __init__(self, session: GaudeamSession, media_id: str, properties: dict):
        self._session = session
        self._media_id = media_id
        self._properties = properties

    def get_properties(self):
        return self._properties

    def get_download_name(self) -> str:
        return self._properties["uploaded_file"]["file_name"]

    def download(self, file_path: str|Path) -> bool:
        """Downloads a file to a local path

        Args:
            file_path (str | Path): The path to save the file to

        Returns:
            bool: True if the download was successful.
        """
        # TODO: the download link does actually not work
        #file_id = self._properties["uploaded_file"]["id"]
        #url = f"{self._session.url()}/drive/uploaded_files/{file_id}/download"
        
        url = self._properties["uploaded_file"]["original"]["url"]
        response = self._session.client().get(url)
        if response.status_code != 200:
            raise RuntimeError(f"Could not download media '{self._media_id}' on {url}")
        # TODO: error handling

        # Save as binary file
        with open(file_path, "wb") as f:
            f.write(response.content)
        return True


