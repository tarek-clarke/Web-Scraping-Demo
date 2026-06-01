import httpx

class SpaceXAPI:
    def fetch_data(self) -> dict:
        """
        Fetches latest launch or capsule info from SpaceX API or returns standardized fallback.
        """
        url = "https://api.spacexdata.com/v4/launches/latest"
        try:
            with httpx.Client() as client:
                response = client.get(url, timeout=5.0)
                if response.status_code == 200:
                    data = response.json()
                    name = data.get("name")
                    flight = data.get("flight_number")
                    # Find a capsule if listed, or use capsule key representation
                    capsules = data.get("capsules", [])
                    capsule_id = capsules[0] if capsules else "C108"
                    return {
                        "canonical": "capsule_serial",
                        "value": str(capsule_id),
                        "metadata": {
                            "flight_number": flight,
                            "launch_name": name,
                            "date_utc": data.get("date_utc")
                        }
                    }
        except Exception:
            pass
            
        # Standardized Mock Fallback
        return {
            "canonical": "capsule_serial",
            "value": "C108",
            "metadata": {
                "flight_number": 108,
                "launch_name": "CRS-21",
                "date_utc": "2020-12-06T16:17:08.000Z",
                "is_fallback": True
            }
        }
