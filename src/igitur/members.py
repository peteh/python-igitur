from .core import IgiturError
from .session import GaudeamSession


class GaudeamMember:
    def __init__(self, session: GaudeamSession, member_id: str, properties: dict):
        self._session = session
        self._member_id = member_id
        if properties is None:
            raise ValueError("Properties must be provided when creating a GaudeamMember instance.")
            #self._properties = self._get_properties()
        else:
            self._properties = properties

    def _get_properties(self) -> dict:
        # TODO: does not work yet, because the API endpoint is not implemented in gaudeam. For now, we require properties to be passed in the constructor.
        url = f"{self._session.url()}/api/v1/member/{self._member_id}"
        response = self._session.client().get(url)
        if response.status_code == 200:
            return response.json()
        else:
            raise IgiturError(f"Error fetching member properties for member '{self._member_id}': {response.status_code}, {response.text}")

    def get_first_name(self) -> str:
        return self._properties.get("first_name", "")

    def get_last_name(self) -> str:
        return self._properties.get("last_name", "")

    def get_email(self) -> str:
        return self._properties.get("email", "")

    def get_phone(self) -> str:
        return self._properties.get("phone_number", "")

    def get_age(self) -> int:
        return int(self._properties.get("age", 0))

    def get_birthdate(self) -> str:
        return self._properties.get("birthdate", "")

    def get_property(self, property_name: str):
        return self._properties.get(property_name, None)

class GaudeamMembers:
    """Member directory of the gaudeam instance. 
    """
    def __init__(self, gaudeam_session: GaudeamSession):
        self._session = gaudeam_session

    def get_members(self, include_dead=False, include_alliances=False, include_resigned=False, seach_term="") -> list[GaudeamMember]:
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

        members_endpoint = f"{self._session.url()}/api/v1/members"
        response_count = self._session.client().get(f"{members_endpoint}/count", params=params)
        if response_count.status_code != 200: 
            raise RuntimeError(f"Error fetching members: {response_count.status_code}, {response_count.text}")
        num_records = response_count.json()["count"]

        gaudeam_members = []
        while len(gaudeam_members) < num_records:
            response_members = self._session.client().get(f"{members_endpoint}/index", params=params)
            if response_members.status_code != 200:
                raise RuntimeError(f"Error fetching members: {response_count.status_code}, {response_count.text}")
            gaudeam_members.extend([GaudeamMember(self._session, member["id"], member) for member in response_members.json()["results"]])
            offset += limit
            params["offset"] = offset
        return gaudeam_members
