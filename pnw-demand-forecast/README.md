# Pacific Northwest Electricity Demand Forecaster

Forecast hourly electricity demand for the Bonneville Power Administration
(BPA) balancing authority from weather, comparing a standard ML model with a
Bayesian model that gives honest uncertainty ranges. The models are benchmarked
against EIA's own published day-ahead forecast.

*Work in progress. Modeling done through a test-period evaluation; next is scoring with forecast (not actual) weather.*

## Results (test period: Jan 2025 – Aug 2026, scored once)

| Forecast | MAPE | Bias (MWh) | 90% interval coverage |
|---|---|---|---|
| EIA day-ahead (benchmark) | **1.94%** | +7 | n/a |
| Gradient boosting + weather-adjusted trend | 4.86% | −338 | n/a |
| Bayesian regression | 4.93% | −322 | 59.6% |
| **Bayesian regression + recent-error correction** | **2.68%** | **−8** | **89.6%** |

All models use *actual* weather, so these are best-case numbers next to EIA's, which used weather forecasts.

## What I found

- **Demand stepped up twice in the test period** (through 2025, and again around Dec 2025), roughly as a constant block of extra load at every hour. Weather and calendar features can't see that, so every weather-only model under-predicts by ~320–350 MWh. ([04](notebooks/04_modeling.ipynb))
- **The Bayesian model's intervals were well calibrated on 2024** once the noise was allowed to vary by season x hour (91.9% coverage, every hour of the day within ~89–94%). But they **collapsed to 14–33% coverage from March 2026**, when the level had shifted outside anything seen in training. ([05](notebooks/05_bayesian.ipynb))
- **Three training years can't separate trend, lasting drift and one-off monthly surprises.** Five versions of a time-varying level either broke the sampler or absorbed part of the trend. ([05](notebooks/05_bayesian.ipynb), moving level)
- **Correcting each day from recent actual demand** (the average error of the last 14 days, using only data available a day ahead) nearly halves the test error and restores ~90% coverage. A Bayesian version of the correction did better on 2024 but worse on 2025–26, because its prior expected much smaller offsets (a prior–data conflict). ([06](notebooks/06_plan_b.ipynb))

## Notebooks

| Notebook | What it does |
|---|---|
| [00_api_calls](notebooks/00_api_calls.ipynb) | First pulls from both APIs |
| [01_build_database](notebooks/01_build_database.ipynb) | Raw CSVs into DuckDB |
| [02_data_quality](notebooks/02_data_quality.ipynb) | Missing hours, glitches, decisions; builds `model_hourly` |
| [03_eda](notebooks/03_eda.ipynb) | Trend, daily/weekly/seasonal cycles, holidays, temperature response, EIA benchmark |
| [04_modeling](notebooks/04_modeling.ipynb) | Features, baselines, gradient boosting, trend extrapolation fix, test period |
| [05_bayesian](notebooks/05_bayesian.ipynb) | Bayesian regression in PyMC: design matrix, priors, sampler fixes, calibration, varying noise, moving-level experiments, test period |
| [06_plan_b](notebooks/06_plan_b.ipynb) | Daily level correction from recent demand: simple and Bayesian (conjugate) updates |

The notebooks are working notebooks: they show the tests, failures and decisions in the order they happened, not just the final model. Running notes are in [scratch/NOTES.md](scratch/NOTES.md).

## Data

- [EIA Hourly Electric Grid Monitor (Form EIA-930)](https://www.eia.gov/opendata/browser/electricity/rto/region-data): hourly demand and day-ahead forecast for `BPAT`. Free API key required.
- [Open-Meteo Historical Weather](https://open-meteo.com/en/docs/historical-weather-api): hourly ERA5 reanalysis for four BPA load centers (Eugene, Everett, Kennewick, Vancouver WA). No key.

## Reproducing

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # then paste your EIA key into .env
python -m src.load_data           # pulls both APIs, builds data/grid.duckdb
```

Then run the notebooks in order. Notebook 05's full-data fits take 30–60 minutes each; their samples are saved to `results/*.nc` (not committed) and loaded on later runs. `src/bayes_model.py` holds the final model's design-matrix functions for reuse (notebook 06).

## Next

- Score with **forecast weather** (Open-Meteo historical forecasts) for a fair comparison with EIA
- A prior for the daily correction that can grow when offsets are large (heavier tails, or a Kalman-filter level)
- Streamlit app: pick a day, see the forecast and interval next to actual demand and EIA
