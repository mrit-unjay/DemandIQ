"""
Step 3 - Seasonal demand forecasting + inventory optimization.

1. Builds monthly UNCONSTRAINED demand (units sold + lost sales) per Region x Category.
   Forecasting on sales alone would under-forecast because stock-outs hide true demand.
2. Backtest: train Jan-2023..Dec-2024, test Jan..Dec-2025. Compares:
     - Seasonal Naive (same month last year)      <- the current "business as usual" plan
     - Seasonal Index x Linear Trend (decomposition)
     - Holt-Winters Exponential Smoothing (multiplicative seasonality, damped trend)
     - Ensemble = mean(Seasonal Naive, Seasonal Index + Trend)   <- PRODUCTION MODEL
   The production model is fixed BEFORE looking at test results (no selection leakage).
   Holt-Winters is kept as a benchmark: with only 2 seasonal cycles it over-extrapolates
   the 2024 heatwave spike.
3. Inventory policy simulation at SKU x Region level on actual 2025 demand:
     - Baseline: what actually happened in 2025 (historical receipts, lost sales, stock)
     - Proposed: order-up-to level = forecast + safety stock (z * rel_sigma * forecast * sqrt(LT)),
       region x category forecast split to SKUs by 2024 SKU mix.
4. Refits on all 36 months and produces a Jan-Dec 2026 forecast + stocking plan.

Outputs (../data/): forecast_backtest.csv, model_accuracy.csv, policy_simulation.csv,
                    forecast_2026.csv, stocking_plan_2026.csv, seasonality_index.csv
"""
import sqlite3
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

warnings.filterwarnings("ignore")
DATA = Path(__file__).resolve().parents[1] / "data"
Z_SERVICE = 1.65          # ~95% cycle service level
LEAD_TIME_MONTHS = 1.0    # factory -> regional warehouse


# ------------------------------------------------------------------ data
def load_sku_inventory() -> pd.DataFrame:
    con = sqlite3.connect(DATA / "voltas_dw.db")
    df = pd.read_sql("""SELECT month, region, category, sku, units_sold, lost_sales_units,
                               true_demand, closing_stock, stock_value
                        FROM vw_inventory_health""", con, parse_dates=["month"])
    con.close()
    return df


def load_demand() -> pd.DataFrame:
    con = sqlite3.connect(DATA / "voltas_dw.db")
    df = pd.read_sql("""
        SELECT month, region, category,
               SUM(units_sold)       AS units_sold,
               SUM(lost_sales_units) AS lost_units,
               SUM(true_demand)      AS demand,
               SUM(closing_stock)    AS closing_stock
        FROM vw_inventory_health
        GROUP BY month, region, category
    """, con, parse_dates=["month"])
    con.close()
    return df.sort_values(["region", "category", "month"])


# ------------------------------------------------------------------ models
def seasonal_naive(train: pd.Series, h: int) -> np.ndarray:
    return np.array([train.iloc[-12 + (i % 12)] for i in range(h)], dtype=float)


def seasonal_index_trend(train: pd.Series, h: int) -> np.ndarray:
    """Classic decomposition: deseasonalise with monthly index, fit linear trend, reseasonalise."""
    months = train.index.month
    idx = train.groupby(months).mean() / train.mean()
    deseason = train.values / idx.loc[months].values
    t = np.arange(len(train))
    slope, intercept = np.polyfit(t, deseason, 1)
    future_t = np.arange(len(train), len(train) + h)
    future_months = pd.date_range(train.index[-1] + pd.offsets.MonthBegin(), periods=h, freq="MS").month
    return np.maximum((intercept + slope * future_t) * idx.loc[future_months].values, 0)


def holt_winters(train: pd.Series, h: int) -> np.ndarray:
    y = train.clip(lower=1)  # multiplicative needs > 0
    model = ExponentialSmoothing(y, trend="add", damped_trend=True, seasonal="mul",
                                 seasonal_periods=12, initialization_method="estimated").fit(optimized=True)
    return np.maximum(model.forecast(h).values, 0)


def ensemble(train: pd.Series, h: int) -> np.ndarray:
    return (seasonal_naive(train, h) + seasonal_index_trend(train, h)) / 2


MODELS = {"Seasonal Naive": seasonal_naive,
          "Seasonal Index + Trend": seasonal_index_trend,
          "Holt-Winters": holt_winters,
          "Ensemble": ensemble}
PROD = "Ensemble"


def relative_sigma(actual, pred):
    """Std-dev of percentage forecast error (bounded to keep it sane for tiny months)."""
    pct = (np.asarray(actual) - np.asarray(pred)) / np.maximum(np.asarray(pred), 1)
    return float(np.clip(np.std(pct), 0.05, 0.6))


def wape(actual, pred):
    return np.abs(actual - pred).sum() / max(actual.sum(), 1)


# ------------------------------------------------------------------ inventory policy
def simulate(demand: np.ndarray, target_level: np.ndarray, opening: float):
    """Order-up-to policy: each month top stock up to target_level, then serve demand."""
    stock, lost, closing = opening, [], []
    for d, tgt in zip(demand, target_level):
        stock += max(0.0, tgt - stock)
        sold = min(d, stock)
        lost.append(d - sold)
        stock -= sold
        closing.append(stock)
    return np.array(lost), np.array(closing)


def main():
    df = load_demand()
    sku = load_sku_inventory()
    backtest_rows, acc_rows, sim_rows, fc_rows, plan_rows = [], [], [], [], []

    for (region, cat), g in df.groupby(["region", "category"]):
        y = g.set_index("month")["demand"].astype(float).asfreq("MS")
        train, test = y[:"2024-12"], y["2025-01":]
        h = len(test)

        # ---- backtest all models
        preds = {name: fn(train, h) for name, fn in MODELS.items()}
        for name, p in preds.items():
            acc_rows.append({"region": region, "category": cat, "model": name,
                             "wape": round(wape(test.values, p), 4)})
        for i, m in enumerate(test.index):
            backtest_rows.append({"month": m, "region": region, "category": cat, "actual": test.iloc[i],
                                  **{n: round(p[i], 1) for n, p in preds.items()}})

        # ---- SKU-level policy simulation on 2025 actual demand
        fc = preds[PROD]
        # rel_sigma estimated without peeking at 2025: 2024 actual vs seasonal-naive-from-2023 error
        rel_sigma = relative_sigma(train[-12:].values, train[-24:-12].values)
        gs = sku[(sku.region == region) & (sku.category == cat)]
        mix = gs[gs.month.dt.year == 2024].groupby("sku")["true_demand"].sum()
        mix = mix / mix.sum()
        for code, share in mix.items():
            h_sku = gs[gs.sku == code].set_index("month").sort_index()
            act25 = h_sku.loc["2025"]
            sku_fc = fc * share
            target = sku_fc * (1 + Z_SERVICE * rel_sigma * np.sqrt(LEAD_TIME_MONTHS))
            opening = float(h_sku.loc["2024-12-01", "closing_stock"])
            lost_b, close_b = simulate(act25["true_demand"].values, target, opening)
            unit_val = (act25["stock_value"] / act25["closing_stock"].replace(0, np.nan)).dropna()
            unit_val = unit_val.iloc[0] if len(unit_val) else 0
            sim_rows.append({"region": region, "category": cat, "sku": code,
                             "demand_2025": act25["true_demand"].sum(),
                             "lost_units_actual": act25["lost_sales_units"].sum(),
                             "lost_units_forecast": lost_b.sum(),
                             "avg_stock_actual": act25["closing_stock"].mean(),
                             "avg_stock_forecast": close_b.mean(),
                             "avg_stock_value_actual": act25["closing_stock"].mean() * unit_val,
                             "avg_stock_value_forecast": close_b.mean() * unit_val})

        # ---- refit on full 36 months, forecast 2026
        fc26 = MODELS[PROD](y, 12)
        rel_sigma_full = relative_sigma(test.values, fc)   # 2025 out-of-sample error
        ss = Z_SERVICE * rel_sigma_full * fc26 * np.sqrt(LEAD_TIME_MONTHS)
        band = 1.28 * rel_sigma_full * fc26                # ~80% interval
        for i, m in enumerate(pd.date_range("2026-01-01", periods=12, freq="MS")):
            fc_rows.append({"month": m, "region": region, "category": cat, "model": PROD,
                            "forecast_units": round(fc26[i]), "lower_80": round(max(fc26[i] - band[i], 0)),
                            "upper_80": round(fc26[i] + band[i])})
            plan_rows.append({"month": m, "region": region, "category": cat,
                              "forecast_units": round(fc26[i]), "safety_stock": round(ss[i]),
                              "target_stock_level": round(fc26[i] + ss[i]),
                              "reorder_point": round(fc26[i] * LEAD_TIME_MONTHS + ss[i])})

    # ---- seasonality index (for Excel / Power BI)
    df["month_num"] = df["month"].dt.month
    si = df.groupby(["category", "month_num"])["demand"].mean()
    si = (si / si.groupby(level=0).transform("mean")).round(3).rename("seasonality_index").reset_index()

    bt = pd.DataFrame(backtest_rows)
    sim = pd.DataFrame(sim_rows)
    for name, d in {"forecast_backtest": bt, "model_accuracy": pd.DataFrame(acc_rows),
                    "policy_simulation": sim, "forecast_2026": pd.DataFrame(fc_rows),
                    "stocking_plan_2026": pd.DataFrame(plan_rows), "seasonality_index": si}.items():
        d.to_csv(DATA / f"{name}.csv", index=False)

    # ---- summary
    print("\nPortfolio WAPE by model (2025 backtest, lower is better):")
    for m in MODELS:
        print(f"  {m:24s} {wape(bt['actual'].values, bt[m].values):6.1%}")
    lost_cut = 1 - sim.lost_units_forecast.sum() / sim.lost_units_actual.sum()
    val_cut = 1 - sim.avg_stock_value_forecast.sum() / sim.avg_stock_value_actual.sum()
    print("\nSKU-level policy simulation on 2025 demand (vs actual history):")
    print(f"  Lost sales units     : {sim.lost_units_actual.sum():>10,.0f} -> {sim.lost_units_forecast.sum():>10,.0f}  ({lost_cut:.1%} reduction)")
    print(f"  Avg stock value (Cr) : {sim.avg_stock_value_actual.sum()/1e7:>10,.2f} -> {sim.avg_stock_value_forecast.sum()/1e7:>10,.2f}  ({val_cut:.1%} reduction)")
    fill_a = 1 - sim.lost_units_actual.sum() / sim.demand_2025.sum()
    fill_b = 1 - sim.lost_units_forecast.sum() / sim.demand_2025.sum()
    print(f"  Fill rate            : {fill_a:10.1%} -> {fill_b:10.1%}")


if __name__ == "__main__":
    main()
