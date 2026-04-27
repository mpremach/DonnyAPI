import requests

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

def get_weather(location_name: str):
    """
    Fetches real-time weather data for a specific location.
    If the user asks about the weather, ALWAYS use this tool ONLY. Do NOT attempt to answer weather questions without it.
    If the user specifies a location, ONLY search the weather for that location, Do NOT search for the weather in any other location including the default.
    If the user doesn't specify a location, 
    use the default coordinates for Charlotte, NC
    """

    # Clean data provided from ollama and input as string
    if isinstance(location_name, dict):
        location_name = location_name.get('value', '')
    location_name = str(location_name).split(',')[0].strip()
    
    if not location_name or location_name == "None":
        location_name = "Charlotte"
    
    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={location_name}&count=1&language=en&format=json"
        geo_data = requests.get(geo_url).json()

        if not geo_data.get('results'):
            return f"Sir, I couldn't find {location_name} in the database."

        lat = geo_data['results'][0]['latitude']
        lon = geo_data['results'][0]['longitude']

        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&temperature_unit=fahrenheit"
        print("Getting weather for location:", location_name)
        response = requests.get(weather_url)
        response.raise_for_status()
        data = response.json()

        current = data['current_weather']
        code = current['weathercode']
        
        condition = WEATHER_CODES.get(code, "Unknown conditions")
        
        return {
            "location": location_name,
            "temperature": f"{current['temperature']}°F",
            "condition": condition,
            "wind_speed": f"{current['windspeed']} mph"
        }
    except Exception as e:
        return f"Sir, I'm having trouble reaching the weather satellite: {str(e)}"