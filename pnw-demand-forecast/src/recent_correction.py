"""
The daily level correction built in notebooks/06_recent_demand.ipynb,
collected here so the summary notebook (and an app) can reuse it.

Each day D, shift the forecast by the recent daily errors from days D-1-n ... D-2
(a day-ahead forecast is made during D-1, so D-2 is the last complete day).
    - window_offsets: plain average of the recent daily errors
    - bayes_offsets: Normal-Normal update of the offset (prior pulls it toward 0)
"""

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, root_mean_squared_error


def scores(y_draws, actual, name, mask=None):
    """
    Point forecast (median) and 90% interval scores
    """
    mask = np.ones(len(actual), bool) if mask is None else mask
    lo, hi = np.percentile(y_draws, 5, axis=0), np.percentile(y_draws, 95, axis=0)
    med = np.median(y_draws, axis=0)
    a, lo, hi, med = actual[mask], lo[mask], hi[mask], med[mask]

    return pd.DataFrame({
        "model": [name],
        "mae_mwh": [mean_absolute_error(a, med)],
        "mape_pct": [100 * mean_absolute_percentage_error(a, med)],
        "rmse_mwh": [root_mean_squared_error(a, med)],
        "bias_mwh": [np.mean(med - a)],
        "coverage_pct": [100 * np.mean((a >= lo) & (a <= hi))],
        "width_mwh": [np.mean(hi - lo)],
    }).round(2)


def point_scores(pred, actual, name, mask=None):
    """
    Same scores for a single-number forecast (no interval)
    """
    mask = np.ones(len(actual), bool) if mask is None else mask
    p, a = pred[mask], actual[mask]
    return pd.DataFrame({
        "model": [name],
        "mae_mwh": [mean_absolute_error(a, p)],
        "mape_pct": [100 * mean_absolute_percentage_error(a, p)],
        "rmse_mwh": [root_mean_squared_error(a, p)],
        "bias_mwh": [np.mean(p - a)],
        "coverage_pct": [np.nan],
        "width_mwh": [np.nan],
    }).round(2)


def daily_errors(y_draws, data):
    """
    Daily average error (actual - forecast median), by Pacific date.
    Returns -> (daily series, Pacific date of every hour)
    """
    resid = data["demand_mwh"].values - np.median(y_draws, axis=0)
    dates = data["period_utc"].dt.tz_convert("America/Los_Angeles").dt.date.values
    return pd.Series(resid).groupby(dates).mean(), dates


def window_offsets(daily, n_days):
    """
    Offset for each day = average daily error over days D-1-n ... D-2
    """
    vals = daily.values
    out = np.zeros(len(vals))
    for i in range(len(vals)):
        window = vals[max(0, i - 1 - n_days):max(0, i - 1)]
        out[i] = window.mean() if len(window) else 0.0  #no history yet -> no correction
    return pd.Series(out, index=daily.index)


def bayes_offsets(daily, n_days, prior_sd, day_sd):
    """
    Normal-Normal update of the offset from days D-1-n ... D-2
        prior: offset ~ Normal(0, prior_sd); each day's error ~ Normal(offset, day_sd)
    Returns -> (posterior mean, posterior sd) per day
    """
    vals = daily.values
    post_mean, post_sd = np.zeros(len(vals)), np.zeros(len(vals))
    for i in range(len(vals)):
        x = vals[max(0, i - 1 - n_days):max(0, i - 1)]
        precision = 1 / prior_sd**2 + len(x) / day_sd**2
        post_mean[i] = (x.sum() / day_sd**2) / precision
        post_sd[i] = np.sqrt(1 / precision)
    return pd.Series(post_mean, index=daily.index), pd.Series(post_sd, index=daily.index)


def apply_offsets(y_draws, dates, off_mean, off_sd=None, seed=1145):
    """
    Shift each hour's forecast draws by its day's offset.
    With off_sd, each draw gets its own offset, which widens the interval by the offset's uncertainty.
    """
    rng = np.random.default_rng(seed)
    day_pos = pd.Index(off_mean.index).get_indexer(dates)  #which day each hour belongs to
    shift = np.tile(off_mean.values, (y_draws.shape[0], 1))
    if off_sd is not None:
        shift = shift + rng.normal(size=shift.shape) * off_sd.values
    return y_draws + shift[:, day_pos]
