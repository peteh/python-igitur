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
