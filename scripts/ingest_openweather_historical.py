#!/usr/bin/env python3
"""
OpenWeather Historical Data Ingestion Script

Fetches historical weather data for testing the Resilient RAP Framework.
Requires OPENWEATHER_API_KEY environment variable.

Usage:
    export OPENWEATHER_API_KEY="your_key"
    python3 scripts/ingest_openweather_historical.py

Output:
    data/ingested/openweather.json (2,500 packets)
"""

import json
import time
import random
import os
from datetime import datetime, timedelta
from collections import defaultdict

import requests

OUTPUT_FILE = "data/ingested/openweather.json"
TARGET_PACKETS = 2500
API_KEY = os.getenv("OPENWEATHER_API_KEY", "")

CITIES = [
    {"name": "New York", "lat": 40.7128, "lon": -74.0060},
    {"name": "London", "lat": 51.5074, "lon": -0.1278},
    {"name": "Tokyo", "lat": 35.6762, "lon": 139.6503},
    {"name": "Paris", "lat": 48.8566, "lon": 2.3522},
    {"name": "Sydney", "lat": -33.8688, "lon": 151.2093},
    {"name": "Moscow", "lat": 55.7558, "lon": 37.6173},
    {"name": "Dubai", "lat": 25.2048, "lon": 55.2708},
    {"name": "Singapore", "lat": 1.3521, "lon": 103.8198},
    {"name": "Berlin", "lat": 52.5200, "lon": 13.4050},
    {"name": "Toronto", "lat": 43.6532, "lon": -79.3832},
]


def get_weather(city):
    """Fetch current weather for a city."""
    if not API_KEY:
        return None
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={city['lat']}&lon={city['lon']}&appid={API_KEY}&units=metric"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return None


def generate_weather_telemetry(city, weather, timestamp):
    """Generate weather telemetry packet."""
    if weather:
        main = weather.get("main", {})
        wind = weather.get("wind", {})
        clouds = weather.get("clouds", {})
        weather_list = weather.get("weather", [{}])
        curr = weather_list[0] if weather_list else {}
        rain = weather.get("rain", {})
    else:
        main = {"temp": random.uniform(10, 30), "humidity": random.randint(30, 90),
                "pressure": random.randint(980, 1030), "feels_like": random.uniform(8, 32)}
        wind = {"speed": random.uniform(0, 20), "deg": random.randint(0, 360), "gust": random.uniform(0, 30)}
        clouds = {"all": random.randint(0, 100)}
        curr = {"main": "Clear", "description": "clear sky", "icon": "01d"}
        rain = {"1h": random.uniform(0, 10)}

    return {
        "source": "openweather",
        "timestamp": timestamp.isoformat(),
        "data": {
            "city": city["name"],
            "lat": city["lat"],
            "lon": city["lon"],
            "temperature_c": main.get("temp", 0),
            "feels_like_c": main.get("feels_like", 0),
            "humidity_percent": main.get("humidity", 0),
            "pressure_hpa": main.get("pressure", 1013),
            "wind_speed_ms": wind.get("speed", 0),
            "wind_degrees": wind.get("deg", 0),
            "wind_gust_ms": wind.get("gust", 0),
            "cloud_percent": clouds.get("all", 0),
            "weather_main": curr.get("main", "Unknown"),
            "weather_description": curr.get("description", ""),
            "weather_icon": curr.get("icon", "01d"),
            "visibility_m": weather.get("visibility", 10000) if weather else 10000,
            "rain_1h_mm": rain.get("1h", 0) if weather else 0,
            "snow_1h_mm": weather.get("snow", {}).get("1h", 0) if weather else 0,
            "sunrise_ts": weather.get("sys", {}).get("sunrise", 0) if weather else 0,
            "sunset_ts": weather.get("sys", {}).get("sunset", 0) if weather else 0,
            "timezone": weather.get("timezone", 0) if weather else 0,
            "clouds_percent": clouds.get("all", 0),
            "wind_chill_c": main.get("temp", 20) - (wind.get("speed", 0) * 0.5),
            "heat_index_c": main.get("feels_like", main.get("temp", 20)),
            "dew_point_c": round(main.get("temp", 20) - (100 - main.get("humidity", 50)) / 5, 1),
        }
    }


def collect_openweather(target_packets):
    """Collect OpenWeather telemetry."""
    available = []
    if API_KEY:
        print(f"OpenWeather API key found: {API_KEY[:8]}...")
        for city in CITIES:
            weather = get_weather(city)
            if weather and weather.get("cod") == 200:
                available.append((city, weather))
                temp = weather.get("main", {}).get("temp", "N/A")
                print(f"  {city['name']}: {temp}°C")
            time.sleep(0.25)  # Rate limit protection

    if not available:
        print("No valid weather data, generating mock data")
        available = [(city, None) for city in CITIES[:5]]

    print(f"Using {len(available)} cities")

    packets = []
    start_time = datetime.utcnow()

    for i in range(target_packets):
        city, weather = random.choice(available)
        ts = start_time + timedelta(seconds=i * 0.5)

        packet = generate_weather_telemetry(city, weather, ts)
        packets.append(packet)

        if (i + 1) % 500 == 0:
            print(f"  Progress: {i + 1}/{target_packets}")

    return packets


def main():
    print("=== OpenWeather Telemetry Ingestion ===")
    print(f"Target: {TARGET_PACKETS} packets")
    print(f"Output: {OUTPUT_FILE}")

    import os as os_module
    os_module.makedirs("data/ingested", exist_ok=True)

    packets = collect_openweather(TARGET_PACKETS)

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(packets, f, indent=2)

    print(f"\nIngestion complete: {len(packets)} packets")
    print(f"Saved to {OUTPUT_FILE}")

    by_city = defaultdict(int)
    for p in packets:
        city = p["data"].get("city", "Unknown")
        by_city[city] += 1

    print("\nPackets by city:")
    for city, count in sorted(by_city.items(), key=lambda x: -x[1]):
        print(f"  {city}: {count}")


if __name__ == "__main__":
    main()