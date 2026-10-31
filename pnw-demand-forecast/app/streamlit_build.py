"""
PNW demand forecast in Streamlit: 
    This will be a slide-style walkthrough of the project with a day explorer.

"""
#imports
import datetime as dt

import pandas as pd
import plotly.graph_objects as go #interactive
import streamlit as st #app

from app_data import build_all, WINDOW #get the data for this

st.set_page_config(page_title="PNW Demand Forecast", layout="wide") #set page setting 

#one color per forecast and keep same across
COLORS = {
    "actual": "#f0f0f0" if st.context.theme.type == "dark" else "#111111",  #follows the viewer's light/dark theme
    "eia": "#7f7f7f",
    "gbm": "#9467bd",
    "m4": "#1f77b4",
    "avg": "#ff7f0e",
    "bayes": "#2ca02c",
}
#what everything will be called
NAMES = {
    "eia": "EIA day-ahead",
    "gbm": "GBM + trend",
    "m4": "Bayesian m4, no correction",
    "avg": f"m4 + average error, last {WINDOW} days",
    "bayes": "m4 + Bayesian update",
}
#first we will get the data and values we want to show 
#then setup the data to present with streamlit
#after this we build the slides

#use streamlit to store and hold data for quicker response
@st.cache_data(show_spinner="Loading the data and saved model samples...")
def get_data():
    """Function to call built function that pulls data"""
    return build_all()

#make call to actually get data
d = get_data()
hourly = d["hourly"] #hourly
scored = hourly[hourly["has_eia"]] #hourly with EIA


def fmt_table(t):
    """
    Function to format the table given to it to better match output
    """
    #rename to have more useful text
    t = t.rename(columns={"model": "forecast", "mae_mwh": "MAE (MWh)", "mape_pct": "MAPE (%)", "rmse_mwh": "RMSE (MWh)",
                          "bias_mwh": "bias (MWh)", "coverage_pct": "90% coverage (%)", "width_mwh": "interval width (MWh)"})
    return as_text(t, 2) #calls function to turn numbers to text


def as_text(t, digits):
    """
    Functions to turn numbers to text with a dash where a forecast has no interval 
       - Streamlit shows NaN as 'None'
    Returns updated table
       """
    t = t.copy()
    for col in t.columns[1:]:
        t[col] = t[col].map(lambda x: "–" if pd.isna(x) else f"{x:,.{digits}f}") #NaN become -
    return t


def layout(fig, title, ytitle, height=380):
    """
    Function for the shared plotly figueres
        We can change how plots look without touching the data here
    """
    #title at the very top
    #legend in the band between the title and the plot
    fig.update_layout(title=dict(text=title, y=0.98, yanchor="top"), yaxis_title=ytitle, height=height + 60,
                      margin=dict(l=10, r=10, t=120 if title else 70, b=10),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0), hovermode="x unified")
    return fig


def monthly(prefix):
    """
    Monthly bias (forecast - actual) and 90% coverage on the hours with an EIA forecast
    """
    g = scored.assign(err=scored[f"{prefix}_med"] - scored["actual"], #add two columns: error and if demand within 90% range
                      inside=(scored["actual"] >= scored[f"{prefix}_lo"]) & (scored["actual"] <= scored[f"{prefix}_hi"]))
    
    return g.groupby("month")["err"].mean(), g.groupby("month")["inside"].mean() * 100


def monthly_point(col):
    """
    Monthly bias for a forecast that is one number per hour (EIA, GBM)
        no interval so there is no coverage to get, only bias
    """
    return (scored[col] - scored["actual"]).groupby(scored["month"]).mean()


def bias_fig(keys, title):
    """
    Function to plot bias
        keys are the short names from NAMES/COLORS for which forecasts to draw
        go.Figure() is an empty chart and each add_scatter adds one line (a "trace")
    Returns the figure with the shared layout
    """
    fig = go.Figure()
    for k in keys:
        #models with an interval use monthly() and take bias [0], the others only have a point forecast
        b = monthly(k)[0] if k in ("m4", "avg", "bayes") else monthly_point(k)
        fig.add_scatter(x=b.index, y=b.values, mode="lines+markers", name=NAMES[k], line=dict(color=COLORS[k])) #name is the legend label
    fig.add_hline(y=0, line_color="gray", line_width=1) #reference line across the plot at zero bias
    return layout(fig, title, "average error (MWh), negative = too low")


def coverage_fig(keys, title):
    """
    Function to plot coverage
        only for the models with an interval (m4, avg, bayes)
    Returns the figure with the shared layout
    """
    fig = go.Figure()
    for k in keys:
        c = monthly(k)[1] #[1] is the coverage part of what monthly() returns
        fig.add_scatter(x=c.index, y=c.values, mode="lines+markers", name=NAMES[k], line=dict(color=COLORS[k]))
    fig.add_hline(y=90, line_dash="dash", line_color="gray", annotation_text="90% target") #the line we want to be on
    fig.update_yaxes(range=[0, 100]) #fix the axis so a drop looks as big as it really is
    return layout(fig, title, "hours inside the 90% interval (%)")


# ---------------------------------------------------------------
# here is the slide info
# ---------------------------

def slide_overview():
    """
    Function to describe the overview
        Each call writes on the page where it currently is at
        Title is title of project
        Markdown is written text after what is called - renders as markdown i.e ** for bold
        caption is small grey text or a caption for what comes before it
        columns is a list of side by side areas (columns)
            calling column again fills it 
        dataframe makes an interactive table 
    """
    #create title and more detailed information
    st.title("Forecasting Pacific Northwest Electricity Demand")
    st.markdown("Hourly demand for the **Bonneville Power Administration (BPA)**, forecast a day ahead from weather "
                "and the calendar, with a 90% range around each hour. EIA's own day-ahead forecast is the benchmark.")

    #pull the data from table for values we need
    #Get final model, the eia, simple bayesian 
    t = d["test_scores"].set_index("model")
    final = t.loc[f"m4 + average error w/ last {WINDOW} days"] #names must match app_data.py exactly
    base = t.loc["Bayesian m4 w/ no correction"]
    eia = t.loc["EIA day-ahead (benchmark)"]

    #new header for data
    st.subheader("Test period is Jan 2025 - Aug 2026 and we scored once")
    c = st.columns(4) #create 4 columns
    #fill with metric data: metric(label, value, delta, delta_color) shows number with colored note underneath
    # use "inverse" in color to make a negative change green which is good hear since lower MAPE is better
    c[0].metric("Final model MAPE", f"{final['mape_pct']:.2f}%", f"{final['mape_pct'] - base['mape_pct']:.2f} pts vs no correction",
                delta_color="inverse")
    c[1].metric("EIA day-ahead MAPE", f"{eia['mape_pct']:.2f}%")
    c[2].metric("Final model bias", f"{final['bias_mwh']:+.0f} MWh", f"from {base['bias_mwh']:+.0f} MWh", delta_color="off")
    c[3].metric("90% interval coverage", f"{final['coverage_pct']:.1f}%", f"from {base['coverage_pct']:.1f}%", delta_color="off")

    #what we want to say!
    st.markdown("""
1. **Weather and the calendar explain demand well.** On 2024 the Bayesian model was within 2.7% and its 90% intervals held 92% of the time.
2. **During the test period, demand moved up to a new level twice.** Weather can't see that, so every weather-only model fell about 320-340 MWh short and the intervals stopped holding.
3. **Correcting each day by the model's recent errors**, using only data available a day ahead, cuts the error almost in half and brings coverage back to 90%. EIA is still better.
""")
    st.caption("Data: EIA-930 Hourly Grid Monitor (balancing authority BPAT) and Open-Meteo hourly reanalysis weather, 2021 - Aug 2026. "
               "Train 2021-2023, choose settings on 2024, score the test period once.")

#
def slide_drivers():
    """
    Function for what drives demand (the EDA from notebook 03)
        header is a heading one size smaller than title
        plotly_chart draws an interactive plotly figure
            width="stretch" makes it fill the column it is in
        three charts side by side then the notes under them
    """
    st.header("What drives demand")
    c = st.columns(3) #3 equal columns, one per chart

    #chart 1: daily shape for winter vs summer
    fig = go.Figure()
    for season, color in [("Winter (Dec–Feb)", "#d62728"), ("Summer (Jun–Aug)", "#1f77b4")]:
        s = d["shape"][d["shape"]["season"] == season] #keep only this season's rows
        fig.add_scatter(x=s["hour_pacific"], y=s["demand_mwh"], mode="lines+markers", name=season, line=dict(color=color))
    fig.update_xaxes(title="hour of day (Pacific)")
    c[0].plotly_chart(layout(fig, "Daily shape depends on the season", "average demand (MWh)"), width="stretch")

    #chart 2: the temperature V
    #go.Figure(go.Scatter(...)) builds the figure and its one line in one step, same as add_scatter
    v = d["v"]
    fig = go.Figure(go.Scatter(x=v["temp_bin"], y=v["mean"], mode="lines+markers", name="demand", line=dict(color=COLORS["m4"])))
    fig.add_vline(x=60, line_dash="dash", line_color="gray", annotation_text="60 °F") #mark the balance point
    fig.update_xaxes(title="average temperature, 4 locations (°F)")
    c[1].plotly_chart(layout(fig, "Demand rises on both sides of ~60 °F", "average demand (MWh)"), width="stretch")

    #chart 3: growth, Jan-Aug average by year
    j = d["jan_aug"]
    #text puts the value on each bar and texttemplate formats it with a comma and no decimals
    fig = go.Figure(go.Bar(x=j["year"].astype(str), y=j["demand_mwh"], text=j["demand_mwh"].round(0), texttemplate="%{text:,.0f}",
                           marker_color=COLORS["m4"]))
    #y axis doesn't start at 0 so growth is visible, the labels show the real values
    fig.update_yaxes(range=[j["demand_mwh"].min() - 600, j["demand_mwh"].max() + 300])
    c[2].plotly_chart(layout(fig, "Demand is growing, fastest in 2025–26", "average demand, Jan–Aug (MWh)"), width="stretch")

    #what we want to say!
    st.markdown("""
- **Daily shape changes with the season**: winter has morning and evening heating peaks, summer one late-afternoon peak. The model gets a separate level for each season × hour (96 slots).
- **Temperature response is a V**, lowest around 58-60 °F. Splitting temperature into **heating and cooling degree-hours** (how far below or above 60 °F), current and 12-hour average, turns each side into a straight line.
- **Demand is growing**, about 15% from 2021 to 2026 (Jan-Aug), with the biggest jumps in 2025 and 2026.
""")


def slide_model():
    """
    Function for the model slide
        code shows text in a monospace box, language=None means no syntax coloring
        columns([1, 1]) is two columns with widths in that ratio
        left side is the model and notes, right side is the weather effects chart
    """
    st.header("The model: Bayesian regression")
    c = st.columns([1, 1])
    #the model written out
    c[0].code("""demand ~ Normal(mu, sigma[slot])
mu = level[slot]
   + weekend + holiday
   + trend x years
   + heating/cooling degree-hours""", language=None)
    c[0].markdown("""
- **`slot`** is one of 96 season x hour-of-day combinations; **trend** is straight-line growth; **degree-hours** are current and 12-hour average, for Everett, Kennewick and Vancouver WA.""")
    c[0].markdown("""
- **Why Bayesian:** it gives a range for every hour and an uncertainty for every effect, so we can check whether the 90% ranges really hold 90% of the time.
- **Priors from domain knowledge (the EDA):** each slot level is centered on 7,000 MWh (± 2,000), and the other weights on Normal(0, 500 MWh).
- **Noise varies by slot**, because winter ramps are harder to predict than spring nights. Each slot's noise is partly pooled toward a shared typical value.
- Fit in PyMC with NUTS on 2021-2024 (35,000 hours).
""")
    #trend with its 90% interval, delta_color="off" keeps the note grey since there is no good/bad direction
    tr = d["trend"]
    c[0].metric("Growth trend", f"{tr['median']:.0f} MWh / year", f"90% interval {tr['lo']:.0f} to {tr['hi']:.0f}", delta_color="off")

    #weather effects chart
    e = d["effects"].iloc[::-1] #reverse so the first feature is at the top (plotly draws categories bottom up)
    #error_x draws the interval: array is how far right of the median (hi - median), arrayminus how far left (median - lo)
    #these are distances not positions, symmetric=False lets the two sides be different lengths
    fig = go.Figure(go.Scatter(x=e["median"], y=e["feature"], mode="markers", marker=dict(color=COLORS["m4"], size=8),
                               error_x=dict(type="data", symmetric=False, array=e["hi"] - e["median"], arrayminus=e["median"] - e["lo"]),
                               name="median and 90% interval"))
    fig.add_vline(x=0, line_color="gray", line_width=1) #zero line, an effect away from it is clearly not 0
    fig.update_xaxes(title="MWh per 10 degree-hours")
    c[1].plotly_chart(layout(fig, "Weather effects with uncertainty", None, height=460), width="stretch")
    c[1].caption("For each location, the current and 12-hour versions add together. Vancouver WA's negative 12-hour cooling effect is "
                 "credit-splitting between two overlapping versions of the same temperature; together they are still about +105.")


def slide_validation():
    """
    Function for the 2024 validation slide
        dataframe makes an interactive table, hide_index drops the 0, 1, 2 row numbers
    """
    st.header("Choosing settings on 2024: the model is calibrated")
    v = d["valid_scores"].set_index("model") #index by name so .loc can look up a row by its name
    #3 headline numbers
    c = st.columns(3)
    c[0].metric("Bayesian m4 MAPE (2024)", f"{v.loc['Bayesian m4', 'mape_pct']:.2f}%")
    c[1].metric("EIA MAPE (2024)", f"{v.loc['EIA day-ahead (benchmark)', 'mape_pct']:.2f}%")
    c[2].metric("90% interval coverage (2024)", f"{v.loc['Bayesian m4', 'coverage_pct']:.1f}%")
    st.dataframe(fmt_table(d["valid_scores"]), hide_index=True, width="stretch") #full table under the numbers
    st.markdown("""
- **The ranges are honest:** 91.9% of 2024's hours fell inside the 90% interval, and every hour of the day was within about 89–94%.
- Notebook 04's gradient boosting was more accurate on 2024 (2.14%), but it gives one number per hour with no range.
- The model already ran about **67 MWh low** in 2024, the first sign the straight-line trend was falling behind.
""")


def slide_shift():
    """
    Function for the test period slide, where the level shifts
        uses the bias_fig and coverage_fig helpers from above
    """
    st.header("Test period: demand moved to a new level")
    c = st.columns(2) #bias on the left, coverage on the right
    c[0].plotly_chart(bias_fig(["m4", "gbm", "eia"], "Monthly bias: every weather-only model falls behind"), width="stretch")
    c[1].plotly_chart(coverage_fig(["m4"], "Monthly coverage: the intervals stop holding"), width="stretch")
    st.markdown("""
- **Demand stepped up twice:** about 80–280 MWh short through most of 2025, then about 290–580 MWh short from December 2025 on. EIA stays within about ±125 MWh.
- **The intervals collapse:** 59.6% coverage overall and 14–33% from March 2026, with almost every miss on the same side (actual demand above the range). The width never reacts.
- The shortfall is about the same in MWh at every hour, which points to **new load that runs around the clock** rather than extra heating or cooling.
""")


def slide_fix():
    """
    Function for the fix slide which is how we improved
        markdown here is an f-string so {WINDOW} and prior_sd get filled in with the real values
    """
    st.header("The fix: correct each day with recent demand")
    #how the correction works
    st.markdown(f"""
For each day **D**:
1. Take the model's average error for each recent day.
2. Use only days up to **D−2**, the last complete day when a day-ahead forecast is made.
3. Shift every hour of D by the average of the last **{WINDOW}** daily errors.

The window was chosen on 2024. A **Bayesian version** starts from a prior that offsets are usually small
(±{d['prior_sd']:.0f} MWh, from 2021–2023), updates on the same days, and widens the range by its uncertainty.
""")
    st.dataframe(fmt_table(d["test_scores"]), hide_index=True, width="stretch") #full test table, full width so no columns get cut

    #same charts as the last slide but now with both corrections added
    c = st.columns(2)
    c[0].plotly_chart(bias_fig(["m4", "avg", "bayes", "eia"], "Monthly bias after the correction"), width="stretch")
    c[1].plotly_chart(coverage_fig(["m4", "avg", "bayes"], "Monthly coverage after the correction"), width="stretch")
    st.markdown("""
- **Error almost halves (4.93% → 2.68%)**, bias drops from −322 to −8 MWh, and coverage returns to about 90%.
- **The simple average beats the Bayesian update**, though the Bayesian one was slightly better on 2024. Its prior expected offsets of about ±120 MWh, but by 2026 the offset was about 570 MWh. The prior keeps pulling the correction back toward zero (a prior–data conflict).
- **EIA is still better.** It also sees recent demand, uses models built for this, and probably has more recent data than the D−2 rule allows.
""")


def slide_explore():
    """
    Function for the explorer slide, the interactive part
        widgets draw a control AND return its current value
            changing one re-runs the whole script and the widget returns the new value
            values reset to the defaults when you leave this slide and come back
        date_input returns a date, radio returns the chosen text,
        multiselect returns a list, toggle returns True/False
    """
    st.header("Explore the test period")
    dates = sorted(hourly["date"].unique()) #every test day, used for the date limits
    c = st.columns([1, 1, 2]) #last column wider for the multiselect

    #the controls
    day = c[0].date_input("Start day", value=dt.date(2026, 1, 12), min_value=dates[0], max_value=dates[-1]) #limits keep it in the test period
    span = c[1].radio("Show", ["1 day", "1 week", "4 weeks"], index=1, horizontal=True) #index=1 starts on "1 week"
    #returns the short keys, format_func only changes what is shown (key -> readable name)
    keys = c[2].multiselect("Forecasts", list(NAMES), default=["eia", "m4", "avg"], format_func=NAMES.get)
    bands = st.toggle("Show 90% intervals", value=True)

    #get the hours to show
    n_days = {"1 day": 1, "1 week": 7, "4 weeks": 28}[span] #dict as a lookup: text -> number of days
    win = hourly[(hourly["date"] >= day) & (hourly["date"] < day + dt.timedelta(days=n_days))]
    if win.empty: #nothing to plot so say so and stop the slide here
        st.info("No data for that range.")
        return

    #plot
    fig = go.Figure()
    for k in keys:
        if k in ("m4", "avg", "bayes"): #models with an interval
            if bands:
                #plotly has no fill between so draw a closed shape:
                #time forward along hi then time backward along lo, fill="toself" fills the inside
                #line width 0 hides the outline, hoverinfo skip keeps it out of the tooltip
                fig.add_scatter(x=pd.concat([win["time"], win["time"][::-1]]), y=pd.concat([win[f"{k}_hi"], win[f"{k}_lo"][::-1]]),
                                fill="toself", fillcolor=COLORS[k], opacity=0.18, line=dict(width=0),
                                name=f"{NAMES[k]}: 90% interval", hoverinfo="skip")
            fig.add_scatter(x=win["time"], y=win[f"{k}_med"], name=NAMES[k], line=dict(color=COLORS[k], width=1.5)) #median line
        else: #EIA and GBM, one number per hour, dashed
            fig.add_scatter(x=win["time"], y=win[k], name=NAMES[k], line=dict(color=COLORS[k], width=1.5, dash="dash"))
    #actual added last so it is drawn on top of everything
    fig.add_scatter(x=win["time"], y=win["actual"], name="Actual", line=dict(color=COLORS["actual"], width=2.5))
    st.plotly_chart(layout(fig, None, "demand (MWh)", height=460), width="stretch")

    #scores for the hours shown
    w = win[win["has_eia"]] #same rule as the notebooks, only hours EIA has a forecast for
    rows = [] #one dict per forecast then turn into a table
    for k in keys:
        pred = w[f"{k}_med"] if k in ("m4", "avg", "bayes") else w[k] #median for interval models
        row = {"forecast": NAMES[k],
               "MAPE (%)": (abs(pred - w["actual"]) / w["actual"]).mean() * 100,
               "bias (MWh)": (pred - w["actual"]).mean()}
        if k in ("m4", "avg", "bayes"): #only models with an interval get coverage, the rest become NaN -> "–"
            row["90% coverage (%)"] = ((w["actual"] >= w[f"{k}_lo"]) & (w["actual"] <= w[f"{k}_hi"])).mean() * 100
        rows.append(row)
    if rows: #empty if every forecast got deselected
        st.dataframe(as_text(pd.DataFrame(rows), 1), hide_index=True, width="stretch")

    #correction used on these days, every hour of a day has the same offset so take the first per day
    off = win.groupby("date")[["avg_offset", "bayes_offset"]].first()
    st.caption(f"Correction applied over these days, from errors up to D−2: average error {off['avg_offset'].min():+.0f} to "
               f"{off['avg_offset'].max():+.0f} MWh, Bayesian update {off['bayes_offset'].min():+.0f} to {off['bayes_offset'].max():+.0f} MWh. "
               "All models here use actual weather, so they are best-case compared with EIA.")


def slide_takeaways():
    """
    Function for the takeaways slide
        subheader inside a column gives each column its own heading
    """
    st.header("Takeaways")
    st.markdown("""
- **Weather and the calendar explain demand well, until the level moves.** On 2024 the model was within 2.7% and calibrated. In 2025–26, two step-ups in demand pushed every weather-only model about 320–340 MWh low.
- **The calibration check is what showed this.** An interval that says 90% and delivers 15% shows exactly what broke: the level, not the weather response or the noise.
- **Recent demand fixes most of it.** A 14-day average of recent errors, using only data available a day ahead, cuts the test error from 4.93% to 2.68% and restores ~90% coverage.
- **The prior has to fit the situation.** The Bayesian correction was slightly better when offsets were small and worse when they grew about 5× larger than its prior expected.
""")
    #limitations and next steps side by side
    c = st.columns(2)
    c[0].subheader("Limitations")
    c[0].markdown("""
- Models use **actual** weather while EIA uses forecast weather, so these numbers are best-case.
- The D−2 rule is conservative; EIA probably uses more recent data.
- One offset per day, which suits the round-the-clock shifts seen in 2025–26.
- Hour-to-hour errors are correlated, so ranges for a whole day or a peak would be too narrow.
""")
    c[1].subheader("Next")
    c[1].markdown("""
- Score with **forecast weather** for a fair comparison with EIA.
- A correction prior that can grow when offsets are large (heavier tails or a Kalman-filter level).
""")


# ------------------------------------------
# navigation: picks the slide and draws it
# -----------------------------------------

#label -> the function that draws it
#no () here so nothing runs yet, these are the functions themselves
SLIDES = {
    "Overview": slide_overview,
    "What drives demand": slide_drivers,
    "The model": slide_model,
    "2024: calibrated": slide_validation,
    "Test: the level shifts": slide_shift,
    "The fix": slide_fix,
    "Explore a day": slide_explore,
    "Takeaways": slide_takeaways,
}
names = list(SLIDES) #labels in order

#session_state is a dict that survives the re-runs (one per browser tab)
#only set the starting slide on the very first run
if "slide" not in st.session_state:
    st.session_state.slide = names[0]


def step(n):
    """
    Function for the Back/Next buttons
        moves the current slide by n (-1 back, +1 next)
        min/max keeps it between the first and last slide
    """
    i = names.index(st.session_state.slide)
    st.session_state.slide = names[min(max(i + n, 0), len(names) - 1)]


#sidebar
#key="slide" ties the radio to st.session_state.slide both ways:
#   clicking an option sets it, and changing it in step() moves the radio
st.sidebar.title("PNW Demand Forecast")
st.sidebar.radio("Slides", names, key="slide")
st.sidebar.caption("Notebooks 00–07 in `notebooks/` show the full working.")

#look up the current slide's function and call it, this draws the slide
SLIDES[st.session_state.slide]()

#Back / Next at the bottom
#on_click runs step() BEFORE the re-run, so the radio already has the new slide when it is drawn
#   using `if st.button(...)` instead would change it after the radio is drawn and Streamlit raises an error
st.divider() #thin line across the page
i = names.index(st.session_state.slide)
c = st.columns([1, 6, 1]) #narrow button columns with the page count in the middle
#args=(-1,) is a 1 item tuple (needs the comma), disabled greys out Back on the first slide and Next on the last
c[0].button("← Back", on_click=step, args=(-1,), disabled=i == 0, width="stretch")
#unsafe_allow_html lets markdown take raw HTML, only used here to center the grey "3 / 8"
c[1].markdown(f"<div style='text-align:center;color:gray'>{i + 1} / {len(names)}</div>", unsafe_allow_html=True)
c[2].button("Next →", on_click=step, args=(1,), disabled=i == len(names) - 1, width="stretch")
