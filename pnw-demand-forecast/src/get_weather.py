""" 
Pull hourly weather from the Open-Meteo API.
No key needed and one request per location covers the full date range.

"""
import time

import pandas as pd
import requests

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive" #this is the base url for the open-meteo api to past data, the other one is for forecast data.
HOURLY_VARS = ['temperature_2m',
               'apparent_temperature',
               'relative_humidity_2m',
               'wind_speed_10m',
               'cloud_cover',
               'shortwave_radiation'] #this can change based on what I want

# LOCATIONS = { #set locations you want to get weather data for, with their lat/lon coordinates. 
#     "Vancouver_wash" : (45.6387, -122.6615),
#     "Portland": (45.5051, -122.6750),
#     "Spokane": (47.6588, -117.4260),
#     "Eugene": (44.0521, -123.0868),
# }
LOCATIONS = { #set locations you want to get weather data for, with their lat/lon coordinates. 
    "Vancouver_wash" : (45.6387, -122.6615),
    "Everett": (47.98, -122.22),
    "Kennewick": (46.21, -119.14),
    "Eugene": (44.0521, -123.0868),
}

#get the archived history data for a given location(s) and date range. 
def fetch_history(lat: float, lon: float, 
                  start_date: str, end_date: str, 
                  hourly_vars: list = None):
    """
    Fetch hourly historical weather data from the Open-Meteo API for a given location and date range.
    Returns a pandas DataFrame with the data in long format and UTC timestamps.
    """
    if hourly_vars is None:
        hourly_vars = HOURLY_VARS

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(hourly_vars),
        "timezone": "UTC",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
    }

    resp = requests.get(ARCHIVE_URL, params=params, timeout=120)
    df = _to_dataframe(resp)
    return df

def fetch_forecast(lat: float, lon: float, 
                   hourly_vars: list = None):
    """
    Fetch hourly weather forecast data from the Open-Meteo API for a given location.
    Returns a pandas DataFrame with the data in long format and UTC timestamps.
    """
    if hourly_vars is None:
        hourly_vars = HOURLY_VARS

    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(hourly_vars),
        "timezone": "UTC",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
    }

    resp = requests.get(FORECAST_URL, params=params, timeout=120)
    df = _to_dataframe(resp)
    return df


def fetch_all_locations(start_date: str, end_date: str, 
                        type: str = "history") -> pd.DataFrame:
    
    """
    Fetch hourly weather data for all predefined locations and a given date range.
    Returns a pandas DataFrame with the data in long format and UTC timestamps.
    """
    type = type.lower()
    if type not in ["history", "forecast"]:
        print(f"Invalid type '{type}' specified. Defaulting to 'history'.")
        print("Valid types are 'history' or 'forecast'.")
        type = "history"

    frames = []
    for name, (lat, lon) in LOCATIONS.items():
        if type == "forecast":
            df = fetch_forecast(lat, lon)
        else:
            df = fetch_history(lat, lon, start_date, end_date)
        df.insert(0, "location", name)
        frames.append(df)
        print(f"weather: {name} -> {len(df):,} hours")
        time.sleep(1)  # be polite to the server
    return pd.concat(frames, ignore_index=True)

def _to_dataframe(resp: requests.Response) -> pd.DataFrame:

    """
    Convert the JSON response from the Open-Meteo API to a pandas DataFrame.
    """
    resp.raise_for_status()
    data = resp.json()
    df = pd.DataFrame(data["hourly"])
    df["time"] = pd.to_datetime(df["time"], utc=True)
    return df.rename(columns={"time": "period_utc"}) 


################################################################################
# UPDATE: 
    #Split into FORECSAST_URL and ARCHIVE_URL, since the API has different endpoints for forecast and historical data.
    #Use helpers to load data so no for loop and easier in each function.
    #done above
# def fetch_weather(lat: float, lon: float,
#                   start_date: str, end_date: str, 
#                   hourly_vars: list = None):
#     #dates look like: 2023-01-01

#     #check if given or set to global default
#     if hourly_vars is None:
#         hourly_vars = HOURLY_VARS

#     #need to loop through locations and make a request for each one, 
#     # then combine the dataframes into one long dataframe.

#     frames = []
#     for name, (lat, lon) in LOCATIONS.items():
#     #build params for the request
#         params = {
#             "latitude": lat,
#             "longitude": lon,
#             "start_date": start_date,
#             "end_date": end_date,
#             "hourly": ",".join(hourly_vars), #so it can be a list of variables
#             "timezone": "UTC",  # match EIA's UTC hours so the join is clean
#             "temperature_unit": "fahrenheit",  # US grid-ops audience
#             "wind_speed_unit": "mph",
#         }

#         #make the request to the API
#         resp = requests.get(BASE_URL, params=params, timeout=60)

#         #check if the request was successful
#         # if resp.status_code != 200:
#         #     raise Exception(f"Request failed with status code {resp.status_code}")
#         #request has its own error handling
#         resp.raise_for_status()
#         data = resp.json()
#         df = pd.DataFrame(data["hourly"])  # {"time": [...], "temperature_2m": [...], ...}
#         df["time"] = pd.to_datetime(df["time"], utc=True)
#         df.insert(0, "location", name)
#         frames.append(df.rename(columns={"time": "period_utc"}))
#         print(f"weather: {name} -> {len(df):,} hours")
#         time.sleep(1)
#     #combine all the dataframes into one long dataframe
#     df = pd.concat(frames, ignore_index=True)

#     return df
    