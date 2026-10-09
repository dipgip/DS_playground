"""
Pull data from the EIA API. 
You need an API key to use it. 

The API returns at most 5,000 rows per request, so this pages through the
result with `offset` until it has everything.
"""

import time
import os

import pandas as pd
import requests
from dotenv import load_dotenv

BASE_URL = "https://api.eia.gov/v2/electricity/rto/region-data/data/"
PAGE_SIZE = 5000  # EIA's hard cap per request

def get_api_key() -> str:
    load_dotenv()  # reads .env in the project root into os.environ
    key = os.getenv("EIA_API_KEY")
    if not key:
        raise RuntimeError("EIA_API_KEY not found, check your .env file")
    return key

def _get_page(params: dict, max_tries: int = 4):
    """
    helper to get data and retry on 429 (rate limit) or 5xx (server error) errors.
    """
    for attempt in range(max_tries):
        wait = 5 * 2 ** attempt  #5, 10, 20, 40 seconds

        try:
            resp = requests.get(BASE_URL, params=params, timeout=60)
        except requests.exceptions.Timeout:
            print(f"timed out, retrying in {wait}s")
            time.sleep(wait)
            continue

        #429 = rate limited, 5xx = server problem, both usually temporary
        if resp.status_code == 429 or resp.status_code >= 500:
            print(f"got {resp.status_code}, retrying in {wait}s")
            time.sleep(wait)
            continue

        #not using raise_for_status(), its error message prints the url which has the api key
        if resp.status_code != 200:
            raise Exception(f"Request failed with status code {resp.status_code}: {resp.text[:200]}")

        return resp.json()["response"]

    raise Exception(f"Request still failing after {max_tries} tries")


def fetch_demand(start: str, end: str, 
                 respondent: str = "BPAT", types: list = None):

    """
    Fetch hourly demand (D) and EIA day-ahead forecast (DF), long format
    and return as a pandas dataframe. The dataframe has UTC timestamps.
    """

    #check if given or set to default
    if types is None:
        types = ["D", "DF"]

    #build params for the request
    params = {
    "api_key": get_api_key(),
    "frequency": "hourly",
    "data[0]": "value",
    "facets[respondent][]": respondent,
    "facets[type][]":types,
    "sort[0][column]": "period",
    "sort[0][direction]": "asc", #ascending order 
    "sort[1][column]": "type",
    "sort[1][direction]": "asc",
    "offset": 0,
    "length": PAGE_SIZE,
    "start": start, 
    "end": end,
}

    #page through the results 5000 rows at a time
    all_rows = []
    offset = 0
    while True:
        params["offset"] = offset

        #done in helper function with retry logic
        #resp = requests.get(BASE_URL, params=params, timeout=60)

        #not using raise_for_status(), its error message prints the url which has the api key
        # if resp.status_code != 200:
        #     raise Exception(f"Request failed with status code {resp.status_code}: {resp.text[:200]}")

        #body = resp.json()["response"]

        body = _get_page(params)
        page = body["data"]
        all_rows.extend(page)
        offset += len(page)
        print(f"{offset} / {body['total']}")

        if len(page) == 0 or offset >= int(body["total"]):
            break
        time.sleep(0.5)  # be polite to the server with a short pause
        
    #make dataframe and fix types
    df = pd.DataFrame(all_rows)
    df = pd.DataFrame({
        "period_utc": pd.to_datetime(df["period"], format="%Y-%m-%dT%H", utc=True),
        "respondent": df["respondent"],
        "type": df["type"],
        # Values arrive as strings ; blanks become NaN.
        "value_mwh": pd.to_numeric(df["value"], errors="coerce"),
    })
    
    return df