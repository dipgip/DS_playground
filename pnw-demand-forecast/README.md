# Pacific Northwest Electricity Demand Forecaster

Forecast hourly electricity demand for the Bonneville Power Administration
(BPA) balancing authority from weather, comparing a standard ML model with a
Bayesian model that gives honest uncertainty ranges. The models are benchmarked
against EIA's own published day-ahead forecast.

*Work in progress. Data pipeline done; modeling next.*

## Data

- [EIA Hourly Electric Grid Monitor (Form EIA-930)](https://www.eia.gov/opendata/browser/electricity/rto/region-data): hourly demand and day-ahead forecast for `BPAT`. Free API key required.
- [Open-Meteo Historical Weather](https://open-meteo.com/en/docs/historical-weather-api): hourly ERA5 reanalysis for four BPA load centers. No key.

## Reproducing

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # then paste your EIA key into .env
python -m src.load_data           # pulls both APIs, builds data/grid.duckdb
```
