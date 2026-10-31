"""
Data for Streamlit:
    This script is to run notebook 7 as a script to gather all the data we need and will be used in the app. 

    Everything shown is built once from the database and from the saved samples. 
    We follow the steps shown in the summary notebook

The forecast draws are large so they are reduced to median and 90% interval per hour here and then dropped
to work better for the app.
"""

#imports
import sys
from pathlib import Path

import arviz as az
import duckdb
import numpy as np
import pandas as pd

#get correct pathing
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

#functions used and scaling
from src.bayes_model import load_features, build_X, slot_index, predictive_draws, DEMAND_SCALE, ALL_WEATHER
from src.recent_correction import scores, point_scores, daily_errors, window_offsets, bayes_offsets, apply_offsets

SEED = 1145
WINDOW = 14 #correction window, chosen in notebook 06
PACIFIC = "America/Los_Angeles"
DB_PATH = ROOT / "data" / "grid.duckdb"
RESULTS = ROOT / "results"

#pull out the mediana nd 90% interval
def summarize(y_draws, prefix):
    """
    Given the draws pull out the median and 90% interval per hour
    for the specified weight
    """

    return pd.DataFrame({
        f"{prefix}_med": np.median(y_draws, axis=0),
        f"{prefix}_lo": np.percentile(y_draws, 5, axis=0),
        f"{prefix}_hi": np.percentile(y_draws, 95, axis=0),
    })


def eda_tables(con):
    """
    This function is to summarize the EDA from notebook 3:
        We load the table made and get the data for time, demand, month,
        and then we pull out the daily shape by season, 
        the temperature's V shape, 
        and monthly averages by year
    """
    #get data
    eda = con.sql("""
        SELECT period_utc, demand_mwh, month, hour_pacific,
               (eugene_temp_f + everett_temp_f + kennewick_temp_f + vancouver_wash_temp_f) / 4 AS temp_avg_f
        FROM features_hourly WHERE demand_mwh IS NOT NULL
    """).df()

    #pacific times, years, and months
    local = eda["period_utc"].dt.tz_convert(PACIFIC)
    eda["year"] = local.dt.year
    eda["local_month"] = local.dt.month
    eda = eda[eda["year"] >= 2021]  #the first 8 UTC hours are still Dec 31 2020 in Pacific time

    #seasons of year
    season = eda["month"].map({12: "Winter (Dec-Feb)", 1: "Winter (Dec-Feb)", 2: "Winter (Dec-Feb)",
                               6: "Summer (Jun-Aug)", 7: "Summer (Jun-Aug)", 8: "Summer (Jun-Aug)"})
    #temperature shape
    shape = (eda.assign(season=season).dropna(subset=["season"])
             .groupby(["season", "hour_pacific"])["demand_mwh"].mean().reset_index())

    v = (eda.assign(temp_bin=(eda["temp_avg_f"] // 2) * 2)
         .groupby("temp_bin")["demand_mwh"].agg(["mean", "size"]).reset_index())
    v = v[v["size"] >= 50]

    #monthly averages
    jan_aug = eda[eda["local_month"] <= 8].groupby("year")["demand_mwh"].mean().reset_index()

    return shape, v, jan_aug


def weather_effects(idata):
    """
    This function here is to get the effects of the weather on the model (features)
    and we only pull out the median and 90% intervals for each
        The weights are given in MWh per 10 degre-hours
    """
    #from given data pull out beta posteriors which are the weather effects
    beta = idata.posterior["beta"].sel(feature=ALL_WEATHER) * DEMAND_SCALE

    #turn in to data frame for stated median and 90%interval
    out = pd.DataFrame({
        "median": beta.median(dim=("chain", "draw")).to_series(),
        "lo": beta.quantile(0.05, dim=("chain", "draw")).to_series(),
        "hi": beta.quantile(0.95, dim=("chain", "draw")).to_series(),
    })
    #renaming index to be more descriptive for what it is
    out.index = [c.replace("vancouver_wash", "vancouver_wa").replace("12", " (12h avg)") for c in out.index]

    #get the trend feature seen from the 'years_since_start' param then get its median and 90% interval
    trend = idata.posterior["beta"].sel(feature="years_since_start") * DEMAND_SCALE
    trend = {"median": float(trend.median()), "lo": float(trend.quantile(0.05)), "hi": float(trend.quantile(0.95))}

    #return both the weights and trend with weights indexing reset with 'features'
    return out.reset_index(names="feature"), trend

#okay below is the full walk through to pull all the data together to be used for the app later
def build_all():
    """
    This function is to gather all of the data and processing and put it together
    to display in the streamlit app the steps follow notebook 7 and are:
        1. connect to table to get data
        2. load in the features we are considering: features_hourly + season + degree-hours from the 12h rolling temperature
        3. make split data and load in the run results
        4. get predicted and actual valid data to get result scores (these aren't saved so we re run it on the data)
        5. then get the setting for the bayesian run with recent demand 
        6. apply bayesian method with recent demand to the EIA data
        7. get test scores for all methods: bayesian, gbm, eia, linear
    We now have all the scores from the methods but we need to load the EDA results from the functions above:
        1. 
    """
    con = duckdb.connect(str(DB_PATH), read_only=True)
    con.sql("SET TimeZone = 'UTC'")

    df = load_features(con)
    train, valid, test = (df[df["split"] == s].reset_index(drop=True) for s in ["train", "valid", "test"])
    preds = con.sql("SELECT * FROM predictions_test ORDER BY period_utc").df()
    assert (preds["period_utc"].values == test["period_utc"].values).all()
    has_eia = preds["eia_forecast_mwh"].notna().values

    idata_valid = az.from_netcdf(RESULTS / "idata_m4_full.nc") #fit on 2021–2023
    idata_test = az.from_netcdf(RESULTS / "idata_m4_final.nc") #refit on 2021–2024
    idata_m5e = az.from_netcdf(RESULTS / "idata_m5e_sub.nc")

    #2024 validation: rerun the scores on the data using the run data
    y_va = predictive_draws(idata_valid, build_X(valid), slot_index(valid), seed=SEED)
    a_va = valid["demand_mwh"].values
    eia_va = valid["eia_forecast_mwh"].notna().values
    #score results as we did in other notebooks
    valid_scores = pd.concat([
        point_scores(valid["eia_forecast_mwh"].values, a_va, "EIA day-ahead (benchmark)", eia_va),
        scores(y_va, a_va, "Bayesian m4", eia_va),
    ], ignore_index=True)
    del y_va #make space we only need the results not what got us them

    #settings for the Bayesian correction which come from the training years only
    prior_sd = float(idata_m5e.posterior["shock_sd"].mean()) * DEMAND_SCALE
    y_tr = predictive_draws(idata_valid, build_X(train), slot_index(train), seed=SEED)
    day_sd = daily_errors(y_tr, train)[0].std()
    del y_tr #again make space we have what we need 

    #test period: base forecast and both corrections
    y_te = predictive_draws(idata_test, build_X(test), slot_index(test), seed=SEED)
    a_te = test["demand_mwh"].values

    daily_te, dates_te = daily_errors(y_te, test)
    off_avg = window_offsets(daily_te, WINDOW)
    off_bayes_mean, off_bayes_sd = bayes_offsets(daily_te, WINDOW, prior_sd, day_sd)

    y_avg = apply_offsets(y_te, dates_te, off_avg)
    y_bayes = apply_offsets(y_te, dates_te, off_bayes_mean, off_bayes_sd)

    #get all the scorings!
    test_scores = pd.concat([
        point_scores(preds["eia_forecast_mwh"].values, a_te, "EIA day-ahead (benchmark)", has_eia),
        scores(y_avg, a_te, f"m4 + average error w/ last {WINDOW} days", has_eia),
        scores(y_bayes, a_te, f"m4 + Bayesian update w/ last {WINDOW} days", has_eia),
        point_scores(preds["pred_gbm"].values, a_te, "GBM + weather-adjusted trend", has_eia),
        scores(y_te, a_te, "Bayesian m4 w/ no correction", has_eia),
        point_scores(preds["pred_linear"].values, a_te, "Linear regression", has_eia),
        point_scores(preds["pred_last_week"].values, a_te, "Same hour last week", has_eia),
    ], ignore_index=True)

    #hourly dataframe used for plotting contains times and actual data as well as predicted
    #combines this with the summary data of results
    hourly = pd.concat([
        pd.DataFrame({
            "time": test["period_utc"].dt.tz_convert(PACIFIC),
            "date": dates_te,
            "actual": a_te,
            "eia": preds["eia_forecast_mwh"].values,
            "gbm": preds["pred_gbm"].values,
            "has_eia": has_eia,
        }),
        #add in the summary data which is the median and 90% intervals with the above
        summarize(y_te, "m4"),
        summarize(y_avg, "avg"),
        summarize(y_bayes, "bayes"),
    ], axis=1)

    #
    hourly["month"] = hourly["time"].dt.strftime("%Y-%m")
    hourly["avg_offset"] = off_avg.reindex(hourly["date"]).values
    hourly["bayes_offset"] = off_bayes_mean.reindex(hourly["date"]).values
    del y_te, y_avg, y_bayes

    #get V shape and weather effects from table and data
    shape, v, jan_aug = eda_tables(con)
    effects, trend = weather_effects(idata_test)
    con.close()

    #return the hourly data, scores, shape, weather effects, trend, months, errors for recent demand
    #tables made above and part needed as a dictionary to access in the building of the app
    return {
        "hourly": hourly,
        "valid_scores": valid_scores,
        "test_scores": test_scores,
        "shape": shape, "v": v, "jan_aug": jan_aug,
        "effects": effects, "trend": trend,
        "prior_sd": prior_sd, "day_sd": day_sd,
    }
