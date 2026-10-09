"""
Download EIA demand + Open-Meteo weather and build data/grid.duckdb.

Usage:
    python -m src.load_data

Re-running is safe — it skips any raw file already present in data/raw/.
Delete a file there to force a fresh pull.
"""

from pathlib import Path

import duckdb

from src.get_eia import fetch_demand
from src.get_weather import fetch_all_locations

#pathing to the data directory and raw directory
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "grid.duckdb"

#date range for the data to be pulled, change if desired
START_DATE = "2021-01-01"
END_DATE = "2026-08-31"

#save csv file names to the raw directory
EIA_CSV = RAW_DIR / "eia_bpat_hourly.csv"
WEATHER_CSV = RAW_DIR / "weather_hourly.csv"


def download_raw() -> None:
    #make data/raw directory if it doesn't exist
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if EIA_CSV.exists():
        print(f"skip (already present): {EIA_CSV.name}")
    else:
        print("downloading EIA demand ...")
        fetch_demand(f"{START_DATE}T00", f"{END_DATE}T23").to_csv(EIA_CSV, index=False)

    if WEATHER_CSV.exists():
        print(f"skip (already present): {WEATHER_CSV.name}")
    else:
        print("downloading Open-Meteo weather ...")
        fetch_all_locations(START_DATE, END_DATE).to_csv(WEATHER_CSV, index=False)


def build_database() -> None:

    con = duckdb.connect(str(DB_PATH))

    #EIA data, long format: one row per (hour, type)
    con.sql(f"""
        CREATE OR REPLACE TABLE eia_raw AS
        SELECT * FROM read_csv_auto('{EIA_CSV}')
    """)

    #open-meteo data, long format: one row per (location, hour)
    con.sql(f"""
        CREATE OR REPLACE TABLE weather_raw AS
        SELECT * FROM read_csv_auto('{WEATHER_CSV}')
    """)

    #quick check that both tables loaded
    for table in ("eia_raw", "weather_raw"):
        n = con.sql(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{table}: {n:,} rows")

    con.close()


if __name__ == "__main__":
    download_raw()
    build_database()
    print(f"done -> {DB_PATH}")