# Working notes

Running log.

## Data pull (2026-10-01)

- **EIA endpoint:** `electricity/rto/region-data`, respondent `BPAT`, types `D` (demand) and `DF` (EIA day-ahead forecast). `DF` is a free baseline: "beat the forecast BPA already publishes" is the business framing.
- **What BPAT is and isn't:** it's BPA's *balancing authority* area, which is not the same as "the PNW". Seattle City Light, Puget Sound Energy, Portland General, Avista, Tacoma, and the Grant/Chelan/Douglas PUDs report as separate BAs. So BPAT load is mostly public utilities and rural/industrial load. This affects which weather locations make sense.
- **Weather locations** (REPLACES SEE BELOW): Eugene, Portland, Spokane, Vancouver_wash. Stored long by location so SQL can average or weight them later. 
- **Time:** both sources pulled in UTC and joined on the UTC hour.
- **Open question:** EIA-930 hours are nominally "hour ending" and Open-Meteo values are instantaneous at the timestamp, so there may be a 1-hour offset. It probably barely matters for temperature, but check it once by cross-correlating demand with temperature.
- **Weather:** 4 × 49,656 hours, no nulls.

## First DuckDB check

Range 2021-01-01 00:00 to 2026-08-31 23:00 UTC = 49,656 expected hours per series.

- **EIA total:** 99,240 rows.
- **Demand (D):** 49,656 rows, so every hour is present, but **49 rows have a NULL value_mwh** (row exists, number is blank). No zeros. TODO: are the 49 NULLs scattered or bunched together?
- **Forecast (DF):** 49,584 rows, so **72 hours (3 days) are missing entirely**. TODO: find which hours with the missing-hours query 
- Correction: an earlier note said "about 36 missing hours per series". That was wrong: D is complete with blanks, DF is missing 72 rows.
- **Weather:** each location has 49,656 rows, so it's complete.
- Still to check: outliers/spikes in D (EIA-930 is known for reporting errors).
- **Gotcha:** DuckDB displays TIMESTAMPTZ in the computer's local time zone (Pacific), so MIN/MAX showed `2020-12-31 16:00-08`. Data is stored correctly in UTC. Run `SET TimeZone = 'UTC'` after connecting.

## Update
- **Locations:** locations used had high correlations (Portland-Vancouver) so dropped Portland to keep BPA data and add more useful coverage of PNW and also dropped Spokane which wasn't BPA either. Using Everett and Kennewick. 
-  **NEW weather locations**: Eugene, Kennewick, Everett, Vancouver due to this caveat: Portland is mostly Portland General Electric territory and Spokane is Avista's, and both report to EIA as separate BAs from BPAT. 