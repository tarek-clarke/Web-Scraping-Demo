import httpx

class OpenMeteoAPI:
    def __init__(self):
        self.lat = 52.52
        self.lon = 13.41

    def fetch_data(self) -> dict:
        """
        Fetches current weather from Open-Meteo or returns a standardized fallback.
        """
        url = f"https://api.open-meteo.com/v1/forecast?latitude={self.lat}&longitude={self.lon}&current_weather=true"
        try:
            with httpx.Client() as client:
                response = client.get(url, timeout=5.0)
                if response.status_code == 200:
                    data = response.json()
                    curr = data.get("current_weather", {})
                    temp = curr.get("temperature")
                    if temp is not None:
                        return {
                            "canonical": "temperature",
                            "value": float(temp),
                            "metadata": {
                                "latitude": self.lat,
                                "longitude": self.lon,
                                "unit": "celsius",
                                "windspeed": curr.get("windspeed"),
                                "winddirection": curr.get("winddirection")
                            }
                        }
        except Exception:
            pass
            
        # Standardized Mock Fallback
        return {
            "canonical": "temperature",
            "value": 21.5,
            "metadata": {
                "latitude": self.lat,
                "longitude": self.lon,
                "unit": "celsius",
                "windspeed": 12.4,
                "winddirection": 220.0,
                "is_fallback": True
            }
        }
