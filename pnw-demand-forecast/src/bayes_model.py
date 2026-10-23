"""
The Bayesian demand model pieces that were built in notebooks/05_bayesian.ipynb,
collected here so can reuse them 

Final model was `m4` in notebook 05:
    demand / 1000 ~ Normal(X @ beta, sigma[season x hour slot])
    X = 96 season x hour slot levels + weekend + major holiday + years_since_start
        + current and 12h heating/cooling degree-hours for Everett, Kennewick, Vancouver WA (scaled / 10)
"""

import numpy as np
import pandas as pd

DEMAND_SCALE = 1000 #model works in thousands of MWh
WEATHER_SCALE = 10  #degree-hours in units of 10

#final weather set from notebook
WEATHER_LOCATIONS = ["everett", "kennewick", "vancouver_wash"]
ALL_WEATHER = [f"{loc}_{kind}" for kind in ["hdh", "cdh", "hdh12", "cdh12"] for loc in WEATHER_LOCATIONS]
CALENDAR = ["is_weekend", "is_major_holiday", "years_since_start"]


def load_features(con):
    """
    features_hourly + season + degree-hours from the 12h rolling temperature 

    """
    locs = ["eugene", "everett", "kennewick", "vancouver_wash"]
    roll12 = ",\n".join(
        f"GREATEST(60 - {loc}_temp_roll12_f, 0) AS {loc}_hdh12, GREATEST({loc}_temp_roll12_f - 60, 0) AS {loc}_cdh12"
        for loc in locs)
    return con.sql(f"""
        SELECT *,
            CASE
                WHEN month IN (12, 1, 2) THEN 0 --winter
                WHEN month IN (3, 4, 5) THEN 1  --spring
                WHEN month IN (6, 7, 8) THEN 2  --summer
                ELSE 3   --fall
            END AS season,
            {roll12}
        FROM features_hourly
        WHERE demand_mwh IS NOT NULL
        ORDER BY period_utc
    """).df()


def design(data, weather_cols=ALL_WEATHER):
    """
    SH model: 
        Intercept + 95 season x hour slot dummies + calendar + weather 
    """
    parts = [pd.DataFrame({"intercept": 1}, index=data.index)]
    sh = pd.Categorical(data["season"] * 24 + data["hour_pacific"], categories=range(96))
    sh_d = pd.get_dummies(sh, prefix="slot", drop_first=True, dtype=int)
    sh_d.index = data.index
    parts.append(sh_d)
    parts.append(data[CALENDAR])
    parts.append(data[weather_cols])
    return pd.concat(parts, axis=1)


def full_slots(X):
    """
    Replace intercept + 95 slot differences with 96 slot levels 
        This is removing the intercept from made model
    """
    X = X.drop(columns="intercept").copy()
    X.insert(0, "slot_0", 1 - X.filter(regex=r"^slot_").sum(axis=1))
    return X


def build_X(data, weather_cols=ALL_WEATHER):
    """
    Design matrix -> scaled weather -> 96 slot levels
    """
    X = design(data, weather_cols).astype(float)
    X[weather_cols] = X[weather_cols] / WEATHER_SCALE
    return full_slots(X)


def slot_index(data):
    """
    Season x hour slot (0-95) for each row same numbering as the slot_ columns
    """
    return (data["season"] * 24 + data["hour_pacific"]).values.astype("int64")


def predictive_draws(idata, X, slots, n_draws=1000, seed=1145):
    """
    Posterior predictive demand (MWh) for the rows of X: 
        X @ beta + noise with that row's slot sigma.

    Same as pm.sample_posterior_predictive for this model 
        done in numpy on a random subset of draws
    
    Returns -> an array (n_draws, n_rows).
    """
    rng = np.random.default_rng(seed)
    beta = idata.posterior["beta"].sel(feature=list(X.columns)).values.reshape(-1, X.shape[1])
    sigma = idata.posterior["sigma"].values.reshape(beta.shape[0], -1)

    keep = rng.choice(beta.shape[0], size=min(n_draws, beta.shape[0]), replace=False)
    mu = beta[keep] @ X.values.T
    noise = rng.normal(size=mu.shape) * sigma[keep][:, slots]

    return (mu + noise) * DEMAND_SCALE
