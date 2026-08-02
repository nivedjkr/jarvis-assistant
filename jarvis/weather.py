"""
OpenWeatherMap Integration Module for JARVIS
Fetches real-time weather conditions and forecasts.
"""

import os
import json
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Dict, Any, Optional, Tuple


class WeatherManager:
    """Manages real weather data queries via OpenWeatherMap API."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        location_config = config.get("location", {})
        self.city = location_config.get("city", "Kerala")
        self.country = location_config.get("country", "India")
        self.api_key = os.getenv("OPENWEATHER_API_KEY", "").strip()
        
        self.last_weather_check: Optional[Dict[str, Any]] = None
        self.last_temp: Optional[float] = None
        self.last_condition: Optional[str] = None

    def _is_configured(self) -> bool:
        """Check if OPENWEATHER_API_KEY is configured."""
        return bool(self.api_key and self.api_key != "your_openweather_api_key_here")

    def fetch_current_weather(self) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Fetch real current weather conditions from OpenWeatherMap.
        Returns (success, message_or_error, weather_dict).
        """
        if not self._is_configured():
            return False, "OpenWeatherMap API key is unconfigured in .env (OPENWEATHER_API_KEY missing).", None

        location_str = f"{self.city},{self.country}" if self.country else self.city
        params = {
            "q": location_str,
            "appid": self.api_key,
            "units": "metric"
        }
        url = f"https://api.openweathermap.org/data/2.5/weather?{urllib.parse.urlencode(params)}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "JARVIS-Assistant/1.0"})
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    temp = data.get("main", {}).get("temp")
                    feels_like = data.get("main", {}).get("feels_like")
                    humidity = data.get("main", {}).get("humidity")
                    weather_desc = data.get("weather", [{}])[0].get("description", "clear")
                    main_condition = data.get("weather", [{}])[0].get("main", "Clear")
                    city_name = data.get("name", self.city)
                    
                    res = {
                        "city": city_name,
                        "temp_c": round(float(temp), 1) if temp is not None else None,
                        "feels_like_c": round(float(feels_like), 1) if feels_like is not None else None,
                        "humidity": humidity,
                        "description": weather_desc,
                        "main_condition": main_condition,
                        "raw": data
                    }
                    self.last_weather_check = res
                    return True, "Current weather retrieved", res
                else:
                    return False, f"OpenWeatherMap returned status code {response.status}", None
        except urllib.error.HTTPError as err:
            if err.code == 401:
                return False, "OpenWeatherMap API Key Unauthorized (HTTP 401). Note: New OpenWeatherMap keys take 10m-2h to activate on OpenWeatherMap servers after creation.", None
            return False, f"OpenWeatherMap HTTP Error {err.code}", None
        except Exception as e:
            return False, f"Weather query failed: {str(e)}", None

    def fetch_forecast_data(self) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Fetch real forecast data from OpenWeatherMap.
        """
        if not self._is_configured():
            return False, "OpenWeatherMap API key is unconfigured in .env.", None

        location_str = f"{self.city},{self.country}" if self.country else self.city
        params = {
            "q": location_str,
            "appid": self.api_key,
            "units": "metric"
        }
        url = f"https://api.openweathermap.org/data/2.5/forecast?{urllib.parse.urlencode(params)}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "JARVIS-Assistant/1.0"})
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    return True, "Forecast retrieved", data
                else:
                    return False, f"Forecast API returned status {response.status}", None
        except urllib.error.HTTPError as err:
            if err.code == 401:
                return False, "OpenWeatherMap API Key Unauthorized (HTTP 401). Note: New OpenWeatherMap keys take 10m-2h to activate on OpenWeatherMap servers after creation.", None
            return False, f"Forecast API HTTP Error {err.code}", None
        except Exception as e:
            return False, f"Forecast query failed: {str(e)}", None

    def get_boot_weather_summary(self) -> str:
        """Get brief current weather summary string for boot greeting."""
        success, _, data = self.fetch_current_weather()
        if success and data and data.get("temp_c") is not None:
            return f"Currently {data['temp_c']}°C, {data['description']} in {data['city']}."
        return ""

    def evaluate_weather_alerts(self) -> Optional[str]:
        """
        Check current conditions and short-term forecast for significant weather events.
        Triggers alert if rain/storm is starting within the next hour or sudden temp shift occurs.
        """
        success, _, curr = self.fetch_current_weather()
        if not success or not curr:
            return None

        alert_msg = None
        curr_temp = curr.get("temp_c")
        curr_main = curr.get("main_condition", "").lower()

        # Check temperature drop/spike (> 5°C shift since last check)
        if self.last_temp is not None and curr_temp is not None:
            temp_diff = curr_temp - self.last_temp
            if abs(temp_diff) >= 5.0:
                direction = "increased" if temp_diff > 0 else "dropped"
                alert_msg = f"Sir, temperature has {direction} by {abs(temp_diff):.1f}°C in {curr['city']}, currently {curr_temp}°C."

        # Check forecast for upcoming rain/storm within 1-2 hours
        f_success, _, f_data = self.fetch_forecast_data()
        if f_success and f_data:
            list_items = f_data.get("list", [])
            if list_items:
                next_item = list_items[0]
                next_weather = next_item.get("weather", [{}])[0].get("main", "").lower()
                next_desc = next_item.get("weather", [{}])[0].get("description", "rain")
                if "rain" in next_weather or "thunderstorm" in next_weather or "snow" in next_weather:
                    if "rain" not in curr_main and "thunderstorm" not in curr_main:
                        alert_msg = f"Sir, {next_desc} expected within the next hour in {curr['city']}."

        self.last_temp = curr_temp
        self.last_condition = curr_main

        return alert_msg

    def format_weather_command(self, is_tomorrow: bool = False) -> str:
        """Format /weather or /weather tomorrow command output."""
        if not self._is_configured():
            return "OpenWeatherMap API key is missing or unconfigured in .env (OPENWEATHER_API_KEY required for real weather data)."

        if not is_tomorrow:
            success, msg, curr = self.fetch_current_weather()
            if not success or not curr:
                return f"Unable to fetch live weather: {msg}"
            
            f_success, _, f_data = self.fetch_forecast_data()
            forecast_summary = ""
            if f_success and f_data:
                today_items = f_data.get("list", [])[:4]  # Next ~12 hours
                temps = [i.get("main", {}).get("temp") for i in today_items if i.get("main", {}).get("temp") is not None]
                descs = list(set([i.get("weather", [{}])[0].get("description") for i in today_items if i.get("weather")]))
                if temps:
                    forecast_summary = f"\nToday's Forecast: High {max(temps):.1f}°C / Low {min(temps):.1f}°C, {', '.join(descs)}."

            return (
                f"=== Weather for {curr['city']} ({self.country}) ===\n"
                f"Current Temp: {curr['temp_c']}°C (Feels like {curr['feels_like_c']}°C)\n"
                f"Condition: {curr['description'].title()}\n"
                f"Humidity: {curr['humidity']}%"
                f"{forecast_summary}"
            )
        else:
            f_success, msg, f_data = self.fetch_forecast_data()
            if not f_success or not f_data:
                return f"Unable to fetch weather forecast: {msg}"

            # Filter forecast items for tomorrow (approx 24h ahead)
            tomorrow_str = (datetime.now().day + 1)
            tomorrow_items = []
            for item in f_data.get("list", []):
                dt_txt = item.get("dt_txt", "")
                try:
                    dt_obj = datetime.strptime(dt_txt, "%Y-%m-%d %H:%M:%S")
                    if dt_obj.day == tomorrow_str:
                        tomorrow_items.append(item)
                except ValueError:
                    pass

            if not tomorrow_items:
                # Fallback to items index 8..16 (~24h out)
                tomorrow_items = f_data.get("list", [])[8:16]

            if not tomorrow_items:
                return f"No forecast data available for tomorrow in {self.city}."

            temps = [i.get("main", {}).get("temp") for i in tomorrow_items if i.get("main", {}).get("temp") is not None]
            descs = list(set([i.get("weather", [{}])[0].get("description") for i in tomorrow_items if i.get("weather")]))
            
            return (
                f"=== Tomorrow's Forecast for {self.city} ({self.country}) ===\n"
                f"Temperature Range: {min(temps):.1f}°C to {max(temps):.1f}°C\n"
                f"Conditions Expected: {', '.join(descs).title()}"
            )
