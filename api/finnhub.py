import httpx
import os

class FinnhubAPI:
    def __init__(self):
        self.api_key = os.getenv("FINNHUB_API_KEY", "sandbox_c8")
        self.symbol = os.getenv("FINNHUB_SYMBOL", "AAPL")

    def fetch_data(self) -> dict:
        """
        Fetches stock quote from Finnhub or returns a standardized fallback.
        """
        url = f"https://finnhub.io/api/v1/quote?symbol={self.symbol}&token={self.api_key}"
        try:
            with httpx.Client() as client:
                response = client.get(url, timeout=5.0)
                if response.status_code == 200:
                    data = response.json()
                    # c = current price
                    price = data.get("c")
                    if price is not None and price != 0:
                        return {
                            "canonical": "price",
                            "value": float(price),
                            "metadata": {
                                "symbol": self.symbol,
                                "currency": "USD",
                                "high": data.get("h"),
                                "low": data.get("l"),
                                "open": data.get("o")
                            }
                        }
        except Exception:
            pass
            
        # Standardized Mock Fallback
        return {
            "canonical": "price",
            "value": 182.50,
            "metadata": {
                "symbol": self.symbol,
                "currency": "USD",
                "high": 184.20,
                "low": 180.80,
                "open": 181.10,
                "is_fallback": True
            }
        }
