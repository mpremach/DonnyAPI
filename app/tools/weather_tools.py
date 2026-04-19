import requests

##NEEDS WORK, NOT USING TOOL

# WMO Weather codes
WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow fall", 73: "Moderate snow fall", 75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail"
}

def get_weather(lat: float = 35.31, lon: float = -80.72):
    """
    Fetches real-time weather data for a specific location.
    If the user doesn't specify a location, 
    use the default coordinates for Charlotte, NC (35.2271, -80.8431).
    """
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&temperature_unit=fahrenheit"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        current = data['current_weather']
        code = current['weathercode']
        
        condition = WEATHER_CODES.get(code, "Unknown conditions")
        
        return {
            "location": "Charlotte, NC",
            "temperature": f"{current['temperature']}°F",
            "condition": condition,
            "wind_speed": f"{current['windspeed']} mph"
        }
    except Exception as e:
        return f"Sir, I'm having trouble reaching the weather satellite: {str(e)}"