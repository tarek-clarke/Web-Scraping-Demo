import httpx

class OpenF1API:
    def __init__(self):
        self.driver_number = 1

    def fetch_data(self) -> dict:
        """
        Fetches F1 driver info from OpenF1 API or returns standardized fallback.
        """
        url = f"https://api.openf1.org/v1/drivers?driver_number={self.driver_number}"
        try:
            with httpx.Client() as client:
                response = client.get(url, timeout=5.0)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list) and len(data) > 0:
                        driver = data[0]
                        full_name = driver.get("full_name")
                        if full_name:
                            return {
                                "canonical": "driver_name",
                                "value": str(full_name),
                                "metadata": {
                                    "driver_number": self.driver_number,
                                    "team_name": driver.get("team_name"),
                                    "country_code": driver.get("country_code")
                                }
                            }
        except Exception:
            pass
            
        # Standardized Mock Fallback
        return {
            "canonical": "driver_name",
            "value": "Max Verstappen",
            "metadata": {
                "driver_number": 33,
                "team_name": "Red Bull Racing",
                "country_code": "NED",
                "is_fallback": True
            }
        }
