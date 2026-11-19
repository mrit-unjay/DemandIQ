"""
Step 1 - Generate realistic synthetic data for a consumer durables business
(ACs, air coolers, refrigerators, washing machines etc.) sold through
distributors and dealers across Indian regions.

Business realism built in:
  * Summer peak for ACs / coolers (Mar-Jun), sharper in North & West
  * South has a longer, flatter summer
  * Monsoon dip (Jul-Sep), festive (Diwali, Oct-Nov) bump for appliances
  * Year-on-year growth, dealer-tier effects, discounts deeper in off-season
  * Inventory planned on last year's pattern -> creates real overstock / stockout
    situations for the forecasting module to detect

Output: CSV files in ../data/
"""
from pathlib import Path
import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)
OUT = Path(__file__).resolve().parents[1] / "data"
OUT.mkdir(exist_ok=True)

START, END = "2023-01-01", "2025-12-31"

# ---------------------------------------------------------------- dimensions
REGIONS = {
    "North":   ["Delhi", "Uttar Pradesh", "Punjab", "Rajasthan", "Haryana"],
    "West":    ["Maharashtra", "Gujarat", "Madhya Pradesh", "Goa"],
    "South":   ["Tamil Nadu", "Karnataka", "Telangana", "Andhra Pradesh", "Kerala"],
    "East":    ["West Bengal", "Odisha", "Bihar", "Jharkhand", "Assam"],
}

# category: (base monthly units per dealer, seasonality by month Jan..Dec)
SEASONALITY = {
    "Split AC":        [0.35, 0.55, 1.30, 2.10, 2.40, 1.80, 0.80, 0.55, 0.55, 0.65, 0.55, 0.40],
    "Window AC":       [0.30, 0.50, 1.25, 2.20, 2.50, 1.70, 0.75, 0.50, 0.50, 0.55, 0.45, 0.35],
    "Air Cooler":      [0.15, 0.40, 1.60, 2.60, 2.70, 1.60, 0.50, 0.30, 0.30, 0.25, 0.15, 0.10],
    "Refrigerator":    [0.80, 0.85, 1.05, 1.20, 1.25, 1.05, 0.85, 0.85, 0.95, 1.25, 1.25, 0.90],
    "Washing Machine": [0.90, 0.85, 0.90, 0.95, 0.95, 0.90, 0.95, 1.00, 1.05, 1.30, 1.35, 1.00],
    "Water Dispenser": [0.55, 0.70, 1.15, 1.50, 1.60, 1.30, 0.90, 0.80, 0.80, 0.85, 0.75, 0.60],
}
REGION_SEASON_STRENGTH = {"North": 1.25, "West": 1.10, "South": 0.70, "East": 0.95}
REGION_SIZE = {"North": 1.15, "West": 1.10, "South": 1.20, "East": 0.75}

PRODUCTS = [
    # sku, category, model, capacity, price(INR)
    ("AC-S-101", "Split AC", "Voltas 1.0T 3-Star Inverter Split", "1.0 Ton", 31990),
    ("AC-S-152", "Split AC", "Voltas 1.5T 3-Star Inverter Split", "1.5 Ton", 36990),
    ("AC-S-155", "Split AC", "Voltas 1.5T 5-Star Inverter Split", "1.5 Ton", 42990),
    ("AC-S-203", "Split AC", "Voltas 2.0T 3-Star Inverter Split", "2.0 Ton", 47990),
    ("AC-W-101", "Window AC", "Voltas 1.0T 3-Star Window", "1.0 Ton", 26490),
    ("AC-W-153", "Window AC", "Voltas 1.5T 3-Star Window", "1.5 Ton", 29990),
    ("CL-D-070", "Air Cooler", "Desert Cooler 70L", "70 L", 11490),
    ("CL-D-090", "Air Cooler", "Desert Cooler 90L", "90 L", 13990),
    ("CL-P-035", "Air Cooler", "Personal Cooler 35L", "35 L", 6990),
    ("CL-T-045", "Air Cooler", "Tower Cooler 45L", "45 L", 8490),
    ("RF-D-260", "Refrigerator", "Frost Free Double Door 260L", "260 L", 27990),
    ("RF-D-340", "Refrigerator", "Frost Free Double Door 340L", "340 L", 36990),
    ("RF-S-190", "Refrigerator", "Direct Cool Single Door 190L", "190 L", 15990),
    ("WM-F-070", "Washing Machine", "Front Load 7kg", "7 kg", 29990),
    ("WM-T-065", "Washing Machine", "Top Load 6.5kg", "6.5 kg", 17990),
    ("WM-S-080", "Washing Machine", "Semi Automatic 8kg", "8 kg", 11990),
    ("WD-B-001", "Water Dispenser", "Bottom Loading Dispenser", "20 L", 12490),
    ("WD-T-001", "Water Dispenser", "Top Loading Dispenser", "20 L", 7990),
]
CAT_BASE_UNITS = {"Split AC": 3.2, "Window AC": 1.6, "Air Cooler": 3.0,
                  "Refrigerator": 1.8, "Washing Machine": 1.6, "Water Dispenser": 0.9}
UNIT_COST_RATIO = {"Split AC": 0.74, "Window AC": 0.76, "Air Cooler": 0.68,
                   "Refrigerator": 0.77, "Washing Machine": 0.78, "Water Dispenser": 0.70}


def build_dims():
    dim_product = pd.DataFrame(PRODUCTS, columns=["sku", "category", "model_name", "capacity", "list_price"])
    dim_product["product_id"] = range(1, len(dim_product) + 1)
    dim_product["unit_cost"] = (dim_product["list_price"] * dim_product["category"].map(UNIT_COST_RATIO)).round(0)
    dim_product = dim_product[["product_id", "sku", "category", "model_name", "capacity", "list_price", "unit_cost"]]

    dist_rows, dealer_rows = [], []
    did, dlid = 1, 1
    for region, states in REGIONS.items():
        for state in states:
            n_dist = 2 if state in ("Maharashtra", "Delhi", "Tamil Nadu", "Uttar Pradesh", "Karnataka", "Gujarat") else 1
            for k in range(n_dist):
                dist_rows.append({
                    "distributor_id": did, "distributor_name": f"{state} Distributors {k + 1}",
                    "region": region, "state": state,
                    "onboarded_date": pd.Timestamp("2018-01-01") + pd.Timedelta(days=int(RNG.integers(0, 1500))),
                    "credit_limit_lakh": int(RNG.choice([50, 75, 100, 150])),
                })
                for _ in range(int(RNG.integers(4, 8))):
                    tier = RNG.choice(["Platinum", "Gold", "Silver"], p=[0.2, 0.35, 0.45])
                    dealer_rows.append({
                        "dealer_id": dlid, "dealer_name": f"Dealer {dlid:03d}",
                        "distributor_id": did, "region": region, "state": state,
                        "city_tier": RNG.choice(["Metro", "Tier 1", "Tier 2", "Tier 3"], p=[0.25, 0.3, 0.3, 0.15]),
                        "dealer_tier": tier,
                    })
                    dlid += 1
                did += 1
    return dim_product, pd.DataFrame(dist_rows), pd.DataFrame(dealer_rows)


def build_sales(dim_product, dim_dealer):
    months = pd.date_range(START, END, freq="MS")
    tier_mult = {"Platinum": 2.2, "Gold": 1.4, "Silver": 0.8}
    dealer_quality = dict(zip(dim_dealer.dealer_id, RNG.lognormal(0, 0.30, len(dim_dealer))))
    rows, inv_no = [], 100000

    for m in months:
        yrs = (m.year - 2023) + m.month / 12
        growth = 1.11 ** yrs
        # 2024 had a hotter, earlier summer -> AC/cooler surge (shows forecast value)
        heatwave = 1.25 if (m.year == 2024 and m.month in (4, 5, 6)) else 1.0
        for d in dim_dealer.itertuples():
            strength = REGION_SEASON_STRENGTH[d.region]
            for p in dim_product.itertuples():
                s = SEASONALITY[p.category][m.month - 1]
                s_adj = 1 + (s - 1) * strength
                hw = heatwave if p.category in ("Split AC", "Window AC", "Air Cooler") else 1.0
                lam = (CAT_BASE_UNITS[p.category] / 3 * s_adj * growth * hw
                       * tier_mult[d.dealer_tier] * REGION_SIZE[d.region] * dealer_quality[d.dealer_id])
                units_month = RNG.poisson(max(lam, 0.01))
                if units_month == 0:
                    continue
                # split monthly units into 1-3 invoices
                n_inv = int(min(units_month, RNG.integers(1, 4)))
                splits = RNG.multinomial(units_month, [1 / n_inv] * n_inv)
                for u in splits:
                    if u == 0:
                        continue
                    day = int(RNG.integers(1, m.days_in_month + 1))
                    off_season = s < 0.9
                    disc = float(np.clip(RNG.normal(0.09 if off_season else 0.04, 0.02), 0, 0.2))
                    gross = u * p.list_price
                    net = round(gross * (1 - disc), 0)
                    rows.append({
                        "invoice_id": f"INV{inv_no}", "invoice_date": m.replace(day=day),
                        "dealer_id": d.dealer_id, "distributor_id": d.distributor_id,
                        "product_id": p.product_id, "units": int(u),
                        "gross_revenue": gross, "discount_pct": round(disc, 4),
                        "net_revenue": net, "cogs": u * p.unit_cost,
                    })
                    inv_no += 1
    sales = pd.DataFrame(rows).sort_values("invoice_date").reset_index(drop=True)
    # inject a few data-quality issues on purpose (cleaned in step 2 - good interview talking point)
    dup = sales.sample(40, random_state=1)
    sales = pd.concat([sales, dup], ignore_index=True)
    sales.loc[sales.sample(25, random_state=2).index, "units"] = np.nan
    sales.loc[sales.sample(10, random_state=3).index, "net_revenue"] = -1
    return sales


def build_inventory_and_targets(sales, dim_product, dim_dealer):
    s = sales.dropna(subset=["units"]).drop_duplicates()
    s = s.merge(dim_dealer[["dealer_id", "region"]], on="dealer_id").merge(dim_product[["product_id", "category"]], on="product_id")
    s["month"] = pd.to_datetime(s["invoice_date"]).dt.to_period("M").dt.to_timestamp()

    # ---- monthly inventory at regional warehouses (product x region)
    demand = s.groupby(["month", "region", "product_id"])["units"].sum().rename("demand").reset_index()
    full = pd.MultiIndex.from_product([pd.date_range(START, END, freq="MS"), list(REGIONS), dim_product.product_id],
                                      names=["month", "region", "product_id"]).to_frame(index=False)
    demand = full.merge(demand, how="left").fillna({"demand": 0}).sort_values(["region", "product_id", "month"])

    inv_rows = []
    for (region, pid), g in demand.groupby(["region", "product_id"]):
        g = g.reset_index(drop=True)
        opening = g.loc[0, "demand"] * 1.2
        for i, r in g.iterrows():
            # naive planning: receipts = same month last year x 1.05 (or recent avg) -> misses heatwaves/shifts
            ly = g.loc[i - 12, "demand"] if i >= 12 else g["demand"].iloc[: max(i, 1)].mean() or r.demand
            receipts = max(0, round(ly * 1.05 * RNG.uniform(0.70, 1.30)))
            available = opening + receipts
            sold = min(r.demand, available)
            lost = r.demand - sold
            closing = available - sold
            inv_rows.append({"month": r.month, "region": region, "product_id": pid,
                             "opening_stock": int(opening), "receipts": int(receipts),
                             "units_sold": int(sold), "lost_sales_units": int(lost),
                             "closing_stock": int(closing)})
            opening = closing
    inventory = pd.DataFrame(inv_rows)

    # ---- monthly targets (region x category) = last-year actual x growth ask, with noise
    act = s.groupby(["month", "region", "category"])["net_revenue"].sum().reset_index()
    act["target_month"] = act["month"] + pd.DateOffset(years=1)
    tgt = act.rename(columns={"net_revenue": "ly_revenue"})
    tgt["target_revenue"] = (tgt["ly_revenue"] * RNG.uniform(1.08, 1.20, len(tgt))).round(-3)
    tgt = tgt[tgt["target_month"] <= END][["target_month", "region", "category", "target_revenue"]]
    tgt = tgt.rename(columns={"target_month": "month"})
    # 2023 targets: set from actuals with small noise (no history)
    a23 = act[act["month"].dt.year == 2023].copy()
    a23["target_revenue"] = (a23["net_revenue"] * RNG.uniform(0.92, 1.10, len(a23))).round(-3)
    targets = pd.concat([a23[["month", "region", "category", "target_revenue"]], tgt], ignore_index=True)
    return inventory, targets


def build_calendar():
    cal = pd.DataFrame({"date": pd.date_range(START, END, freq="D")})
    cal["year"] = cal.date.dt.year
    cal["quarter"] = "Q" + cal.date.dt.quarter.astype(str)
    cal["month_num"] = cal.date.dt.month
    cal["month_name"] = cal.date.dt.strftime("%b")
    cal["month_start"] = cal.date.dt.to_period("M").dt.to_timestamp().dt.date
    # Indian FY: Apr-Mar
    cal["fiscal_year"] = np.where(cal.month_num >= 4, "FY" + (cal.year + 1).astype(str).str[-2:],
                                  "FY" + cal.year.astype(str).str[-2:])
    cal["season"] = cal.month_num.map(lambda m: "Summer (Peak)" if m in (3, 4, 5, 6)
                                      else "Monsoon" if m in (7, 8, 9)
                                      else "Festive" if m in (10, 11) else "Winter")
    return cal


if __name__ == "__main__":
    dim_product, dim_distributor, dim_dealer = build_dims()
    sales = build_sales(dim_product, dim_dealer)
    inventory, targets = build_inventory_and_targets(sales, dim_product, dim_dealer)
    calendar = build_calendar()

    for name, df in {"dim_product": dim_product, "dim_distributor": dim_distributor, "dim_dealer": dim_dealer,
                     "dim_calendar": calendar, "fact_sales_raw": sales, "fact_inventory": inventory,
                     "fact_targets": targets}.items():
        df.to_csv(OUT / f"{name}.csv", index=False)
        print(f"{name:18s} {len(df):>8,} rows")
