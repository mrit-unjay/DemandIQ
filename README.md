# ❄️ Consumer Durables Sales, Channel & Demand Intelligence System

An end-to-end analytics project for a seasonal, high-volume consumer durables business (ACs, air coolers, refrigerators, washing machines, water dispensers). It combines two problem statements into one system:

1. **Sales & Channel Intelligence**: monitor sales, distributor and dealer performance, regional demand and target achievement.
2. **Seasonal Demand Forecasting & Inventory Optimization**: forecast demand by region and category, and flag overstocking and stock-outs before they happen.

**Stack:** Python (pandas, statsmodels) · SQL (star schema, CTEs, window functions) · Excel (formula-driven model) · Power BI (DAX, star schema, what-if) · Streamlit (interactive web app)

> **Data note:** All data is synthetic, generated to mirror the real dynamics of the Indian cooling and appliances market (summer AC peak, monsoon dip, Diwali appliance bump, a 2024 heatwave, dealer tiers, regional differences). No company data is used. Results are illustrative of the method.

---

## Architecture

```
 01_generate_data.py         02_clean_and_load_sql.py        03_forecast_and_inventory.py
 ┌──────────────────┐        ┌───────────────────────┐        ┌────────────────────────────┐
 │ Synthetic raw    │ ─────▶ │ Clean (dupes, nulls,  │ ─────▶ │ Unconstrained demand       │
 │ sales, dealers,  │        │ invalid values)       │        │ 4 models, 2025 backtest    │
 │ inventory,       │        │ Load star schema →    │        │ SKU-level policy simulation│
 │ targets          │        │ SQLite / MySQL / PG   │        │ 2026 forecast + stock plan │
 └──────────────────┘        │ + reporting views     │        └─────────────┬──────────────┘
                             └──────────┬────────────┘                      │
             ┌──────────────────────────┼──────────────────────────────────┤
             ▼                          ▼                                   ▼
   Excel workbook (04_…)       Power BI report (DAX)            Streamlit app (app/)
   formula-driven planner      4 pages, what-if, RLS            4 tabs, live filters
```

| Tool | What it does in this project |
|---|---|
| **SQL** | Star schema (3 facts, 4 dims), 3 reporting views, 12 business queries using CTEs, `LAG`, `ROW_NUMBER`, running totals, moving averages, `CASE` banding |
| **Python** | Data generation, cleaning with an audit log, 4 forecasting models, backtesting, safety stock, SKU-level inventory simulation |
| **Excel** | 1,792 live formulas: year-selector KPI summary (`SUMIFS`), target heatmap, seasonality index, 2026 stocking planner with editable service level (`NORMSINV`), dealer scorecard (`RANK`, `COUNTIFS`) |
| **Power BI** | 55+ DAX measures (time intelligence, Indian FY, Pareto, seasonality index, what-if safety stock), build guide, theme |
| **Streamlit** | Interactive app: executive KPIs, channel scorecards, forecast explorer, inventory planner with a service-level slider and CSV export |

---

## Key findings

**Sales & channel**
- 2025 revenue was flat (₹103.98 Cr vs ₹103.71 Cr) after a 23% jump in 2024, and target achievement fell from **108% to 88%**.
- The root cause is that **2025 targets were set off a heatwave-inflated 2024**. All 12 region-category combinations below 90% of target are cooling products (Split AC, Window AC, Air Cooler); appliances were near or above target. *Recommendation: normalise target baselines for weather anomalies.*
- Summer (Mar–Jun) brings **59% of annual revenue**, so channel readiness and stock pre-build in February are the biggest levers.
- Water Dispensers grew fastest (+16% YoY); Split AC declined 3.5% against its heatwave base.
- 11 dealers declined more than 15% YoY, which the dealer early-warning list surfaces for sales team follow-up.
- Off-season discounts (10%+) cut gross margin by about 4–5 points without materially lifting units per invoice.

**Forecasting & inventory**
- Planning on last year's volume caused **₹23 Cr of lost sales in 2023** (peak stock-outs), then over-correction: average stock value climbed from ₹6.9 Cr to **₹12.6 Cr** by 2025.
- Forecasting is done on **unconstrained demand** (sales + lost sales), because sales alone hide demand during stock-outs.
- 2025 backtest (WAPE, lower is better): Seasonal Naive 12.4% · Seasonal Index + Trend 12.9% · Holt-Winters 31.6% · **Ensemble 11.1%** (production model, fixed before testing to avoid selection bias). Holt-Winters over-extrapolates the 2024 heatwave with only two seasonal cycles.
- Replaying actual 2025 demand at SKU × region level with a forecast-driven order-up-to policy cut **lost sales by ~50%** (870 → 438 units) and **average capital in stock by ~74%** (₹12.6 Cr → ₹3.2 Cr), raising fill rate from 98.0% to 99.0%.

---

## Run it

```bash
pip install -r requirements.txt
python python/run_pipeline.py          # generate → clean → SQL → forecast → Excel (≈1 min)
streamlit run app/streamlit_app.py     # open http://localhost:8501
```

Use MySQL or PostgreSQL instead of SQLite:
```bash
export DB_URL="postgresql+psycopg2://user:pass@localhost:5432/voltas"
python python/02_clean_and_load_sql.py
```
Then run `sql/02_analysis_queries.sql` in your SQL client. Power BI: follow `powerbi/powerbi_build_guide.md`.

**Deploy the app free:** push to GitHub → share.streamlit.io → select `app/streamlit_app.py`. Commit the `data/` folder so the app finds the database.

## Project structure
```
├── app/streamlit_app.py                 Interactive 4-tab web app
├── data/                                Generated CSVs + SQLite warehouse (voltas_dw.db)
├── excel/Voltas_Sales_Demand_Analysis.xlsx
├── powerbi/  dax_measures.dax · powerbi_build_guide.md · voltas_theme.json
├── python/   01_generate_data · 02_clean_and_load_sql · 03_forecast_and_inventory
│             04_build_excel_report · run_pipeline
├── sql/      01_schema · 02_analysis_queries · 03_views
└── requirements.txt
```

---

## Resume entry

**Consumer Durables Sales, Channel & Demand Intelligence System** | Python, SQL, Power BI, Excel, Streamlit
- Built an end-to-end BI system for a seasonal consumer durables business (ACs, coolers, appliances; ₹290 Cr+, 68K invoices, 143 dealers, 25 distributors, 4 regions), modelling a SQL star schema with 12 analytical queries (CTEs, window functions) and reporting views.
- Developed Power BI and Streamlit dashboards tracking revenue, target achievement, distributor/dealer scorecards and inventory health with 55+ DAX measures; identified that 2025's 88% target achievement was driven by heatwave-inflated cooling-category targets.
- Forecast monthly demand by region × category on unconstrained demand, benchmarking 4 models; the ensemble cut forecast error (WAPE) from 12.4% to 11.1% versus last-year-based planning.
- Designed a safety-stock-based stocking policy; a SKU-level simulation on 2025 demand showed ~50% fewer lost sales and ~74% less capital locked in inventory.
- Built a formula-driven Excel planner (1,700+ formulas) with an adjustable service level that recalculates safety stock and order-up-to levels.

*Keep the word "simulated" if asked about the impact numbers. Interviewers respect honesty about synthetic data far more than inflated claims.*

---

## Interview talking points

**Why forecast on unconstrained demand?** When a SKU stocks out, recorded sales drop even though customers wanted it. Training on sales teaches the model to under-forecast exactly the peak months where it matters most, so I add lost sales back.

**Why WAPE instead of MAPE?** Coolers sell near zero in December. MAPE divides by each month's actual, so tiny months explode the error. WAPE weights by volume, which matches business impact.

**Why didn't Holt-Winters win?** Only 24 months of training means two seasonal cycles, and one contained a heatwave. It read the spike as trend. The simpler ensemble was more robust; with 4–5 years of data I would revisit it alongside weather features (temperature forecasts drive AC demand).

**How did you avoid overfitting the model choice?** The production model was fixed before looking at 2025 results. Choosing the best model per series using test data would make the reported accuracy look better than it would be in reality.

**How is safety stock set?** Safety stock = z(service level) × forecast error % × forecast × √lead time. It scales with the forecast, so it is large before the summer peak and small in the off-season. A flat safety stock would overstock winter.

**Data cleaning?** The raw extract had 40 duplicate invoices, 25 null quantities and 10 negative revenue rows; each removal is logged so the numbers reconcile.

**What would you do next with real data?** Add weather and festival calendars as forecast drivers, forecast at SKU level for top sellers, include secondary sales (dealer → consumer) and service/warranty data, and automate a weekly refresh with scheduled SQL loads.
