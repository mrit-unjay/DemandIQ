"""
Voltas Sales, Channel & Demand Intelligence - Streamlit app
Run:  streamlit run app/streamlit_app.py
"""
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DB = DATA / "voltas_dw.db"

st.set_page_config(page_title="DemandIQ : Sales & Demand Intelligence", page_icon="❄️", layout="wide")


# ------------------------------------------------------------------ data
@st.cache_data
def q(sql: str) -> pd.DataFrame:
    with sqlite3.connect(DB) as con:
        return pd.read_sql(sql, con)


@st.cache_data
def load():
    sales = q("""SELECT month, year, month_num, season, region, state, city_tier, dealer_tier,
                        dealer_name, distributor_name, category, sku,
                        SUM(units) units, SUM(net_revenue) revenue, SUM(gross_margin) gm,
                        AVG(discount_pct) avg_disc
                 FROM vw_sales_enriched
                 GROUP BY month, year, month_num, season, region, state, city_tier, dealer_tier,
                          dealer_name, distributor_name, category, sku""")
    sales["month"] = pd.to_datetime(sales["month"])
    tgt = q("SELECT * FROM vw_target_achievement")
    tgt["month"] = pd.to_datetime(tgt["month"])
    inv = q("SELECT * FROM vw_inventory_health")
    inv["month"] = pd.to_datetime(inv["month"])
    bt = pd.read_csv(DATA / "forecast_backtest.csv", parse_dates=["month"])
    fc = pd.read_csv(DATA / "forecast_2026.csv", parse_dates=["month"])
    plan = pd.read_csv(DATA / "stocking_plan_2026.csv", parse_dates=["month"])
    acc = pd.read_csv(DATA / "model_accuracy.csv")
    sim = pd.read_csv(DATA / "policy_simulation.csv")
    hist = q("""SELECT month, region, category, SUM(true_demand) demand
                FROM vw_inventory_health GROUP BY month, region, category""")
    hist["month"] = pd.to_datetime(hist["month"])
    return sales, tgt, inv, bt, fc, plan, acc, sim, hist


if not DB.exists():
    st.error("Database not found. Run the pipeline first:  python python/run_pipeline.py")
    st.stop()

sales, tgt, inv, bt, fc, plan, acc, sim, hist = load()


def cr(x):
    return f"₹{x / 1e7:,.2f} Cr"


# ------------------------------------------------------------------ sidebar
st.sidebar.title("❄️ Filters")
years = sorted(sales.year.unique())
year = st.sidebar.selectbox("Year", years, index=len(years) - 1)
regions = st.sidebar.multiselect("Region", sorted(sales.region.unique()), default=sorted(sales.region.unique()))
cats = st.sidebar.multiselect("Category", sorted(sales.category.unique()), default=sorted(sales.category.unique()))
st.sidebar.caption("Synthetic data modelled on a seasonal consumer durables business, Jan 2023 – Dec 2025.")

if not regions or not cats:
    st.warning("Select at least one region and one category.")
    st.stop()

f = sales[sales.region.isin(regions) & sales.category.isin(cats)]
fy, fp = f[f.year == year], f[f.year == year - 1]
ft = tgt[tgt.region.isin(regions) & tgt.category.isin(cats)]
fty = ft[ft.month.dt.year == year]

st.title(" DemandIQ :Sales, Channel & Demand Intelligence")
tab1, tab2, tab3, tab4 = st.tabs(["📊 Executive Overview", "🤝 Channel Performance",
                                  "📈 Seasonality & Forecast", "📦 Inventory Planning"])

# ================================================================== TAB 1
with tab1:
    rev, rev_p = fy.revenue.sum(), fp.revenue.sum()
    units, units_p = fy.units.sum(), fp.units.sum()
    target = fty.target_revenue.sum()
    gm_pct = fy.gm.sum() / rev if rev else 0
    gm_pct_p = fp.gm.sum() / rev_p if rev_p else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Net revenue", cr(rev), f"{rev / rev_p - 1:+.1%} YoY" if rev_p else None)
    c2.metric("Units sold", f"{units:,.0f}", f"{units / units_p - 1:+.1%} YoY" if units_p else None)
    c3.metric("Target achievement", f"{rev / target:.1%}" if target else "–")
    c4.metric("Gross margin", f"{gm_pct:.1%}", f"{(gm_pct - gm_pct_p) * 100:+.2f} pp" if rev_p else None)
    c5.metric("Active dealers", f"{fy.dealer_name.nunique():,}")

    left, right = st.columns([3, 2])
    with left:
        m = f.groupby("month", as_index=False)[["revenue"]].sum()
        mt = ft.groupby("month", as_index=False)[["target_revenue"]].sum()
        fig = go.Figure()
        fig.add_bar(x=m.month, y=m.revenue / 1e7, name="Actual", marker_color="#1F3A5F")
        fig.add_scatter(x=mt.month, y=mt.target_revenue / 1e7, name="Target", mode="lines",
                        line=dict(color="#E8833A", width=3))
        fig.update_layout(title="Monthly revenue vs target (₹ Cr)", height=380, legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig, width="stretch")
    with right:
        heat = fty.groupby(["region", "category"]).agg(a=("actual_revenue", "sum"), t=("target_revenue", "sum"))
        heat = (heat.a / heat.t).unstack()
        fig = px.imshow(heat, text_auto=".0%", color_continuous_scale="RdYlGn", zmin=0.75, zmax=1.15,
                        aspect="auto", title=f"Target achievement {year} – region × category")
        fig.update_layout(height=380, coloraxis_showscale=False)
        st.plotly_chart(fig, width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        bc = fy.groupby("category", as_index=False).revenue.sum().sort_values("revenue")
        st.plotly_chart(px.bar(bc, x=bc.revenue / 1e7, y="category", orientation="h",
                               labels={"x": "₹ Cr", "category": ""}, title="Revenue by category",
                               color_discrete_sequence=["#1F3A5F"]).update_layout(height=340),
                        width="stretch")
    with c2:
        st.plotly_chart(px.pie(fy.groupby("region", as_index=False).revenue.sum(), values="revenue",
                               names="region", hole=0.5, title="Revenue mix by region")
                        .update_layout(height=340), width="stretch")

    # auto-generated insights
    st.subheader("Key insights")
    worst = (fty.groupby(["region", "category"]).apply(lambda g: g.actual_revenue.sum() / g.target_revenue.sum())
             .sort_values())
    yoy_cat = (fy.groupby("category").revenue.sum() / fp.groupby("category").revenue.sum() - 1).dropna().sort_values()
    bullets = []
    if len(worst):
        bullets.append(f"Biggest target gap: **{worst.index[0][1]} in {worst.index[0][0]}** at {worst.iloc[0]:.0%} of target.")
    if len(yoy_cat):
        bullets.append(f"Fastest-growing category: **{yoy_cat.index[-1]}** ({yoy_cat.iloc[-1]:+.1%} YoY); "
                       f"slowest: **{yoy_cat.index[0]}** ({yoy_cat.iloc[0]:+.1%}).")
    peak = fy[fy.season == "Summer (Peak)"].revenue.sum() / rev if rev else 0
    bullets.append(f"Summer (Mar–Jun) delivers **{peak:.0%}** of the year's revenue – stock and channel readiness "
                   "before March is the single biggest lever.")
    for b in bullets:
        st.markdown(f"- {b}")

# ================================================================== TAB 2
with tab2:
    st.subheader(f"Distributor scorecard – {year}")
    d = fy.groupby(["distributor_name", "region"]).agg(revenue=("revenue", "sum"), gm=("gm", "sum"),
                                                       dealers=("dealer_name", "nunique"),
                                                       avg_disc=("avg_disc", "mean")).reset_index()
    dp = fp.groupby("distributor_name").revenue.sum().rename("rev_prev")
    d = d.merge(dp, on="distributor_name", how="left")
    d["YoY %"] = (d.revenue / d.rev_prev - 1) * 100
    d["GM %"] = d.gm / d.revenue * 100
    d["Revenue (₹ Cr)"] = d.revenue / 1e7
    d["Avg discount %"] = d.avg_disc * 100
    d["Share %"] = d.revenue / d.revenue.sum() * 100
    show = d.sort_values("revenue", ascending=False)[["distributor_name", "region", "dealers", "Revenue (₹ Cr)",
                                                       "YoY %", "GM %", "Avg discount %", "Share %"]]
    st.dataframe(show.style.format({"Revenue (₹ Cr)": "{:.2f}", "YoY %": "{:+.1f}", "GM %": "{:.1f}",
                                    "Avg discount %": "{:.1f}", "Share %": "{:.1f}"})
                 .background_gradient(subset=["YoY %"], cmap="RdYlGn", vmin=-20, vmax=20),
                 width="stretch", hide_index=True, height=320)

    c1, c2 = st.columns(2)
    with c1:
        dr = fy.groupby("dealer_name").revenue.sum().sort_values(ascending=False).reset_index()
        dr["cum_share"] = dr.revenue.cumsum() / dr.revenue.sum()
        dr["dealer_pct"] = (dr.index + 1) / len(dr)
        n80 = int((dr.cum_share < 0.8).sum() + 1)
        fig = px.area(dr, x="dealer_pct", y="cum_share", title=f"Dealer Pareto – {n80} of {len(dr)} dealers "
                                                                f"({n80 / len(dr):.0%}) make 80% of revenue")
        fig.add_hline(y=0.8, line_dash="dash", line_color="red")
        fig.update_layout(height=360, xaxis_tickformat=".0%", yaxis_tickformat=".0%",
                          xaxis_title="Share of dealers", yaxis_title="Cumulative revenue share")
        st.plotly_chart(fig, width="stretch")
    with c2:
        tier = fy.groupby(["dealer_tier", "city_tier"]).revenue.sum().reset_index()
        st.plotly_chart(px.bar(tier, x="dealer_tier", y=tier.revenue / 1e7, color="city_tier",
                               title="Revenue by dealer tier & city tier (₹ Cr)",
                               labels={"y": "₹ Cr", "dealer_tier": "Dealer tier"},
                               category_orders={"dealer_tier": ["Platinum", "Gold", "Silver"]})
                        .update_layout(height=360), width="stretch")

    st.subheader("Early-warning: dealers declining > 15% YoY")
    dd = pd.concat([fy.groupby(["dealer_name", "distributor_name", "region", "dealer_tier"]).revenue.sum().rename("cur"),
                    fp.groupby(["dealer_name", "distributor_name", "region", "dealer_tier"]).revenue.sum().rename("prev")],
                   axis=1).dropna().reset_index()
    dd["change %"] = (dd.cur / dd.prev - 1) * 100
    risk = dd[dd["change %"] < -15].sort_values("change %")
    if len(risk):
        risk["Revenue now (₹ L)"], risk["Revenue LY (₹ L)"] = risk.cur / 1e5, risk.prev / 1e5
        st.dataframe(risk[["dealer_name", "distributor_name", "region", "dealer_tier", "Revenue LY (₹ L)",
                           "Revenue now (₹ L)", "change %"]].style.format(
            {"Revenue LY (₹ L)": "{:.1f}", "Revenue now (₹ L)": "{:.1f}", "change %": "{:+.1f}"}),
            width="stretch", hide_index=True)
    else:
        st.info("No dealers declining more than 15% for the current selection (or no prior-year data).")

    st.subheader("Discount vs margin by season")
    sd = f.groupby(["season", "category"]).agg(disc=("avg_disc", "mean"), gm=("gm", "sum"), rev=("revenue", "sum")).reset_index()
    sd["GM %"] = sd.gm / sd.rev * 100
    sd["Avg discount %"] = sd.disc * 100
    st.plotly_chart(px.scatter(sd, x="Avg discount %", y="GM %", color="season", symbol="category", size="rev",
                               title="Off-season discounting erodes margin").update_layout(height=380),
                    width="stretch")

# ================================================================== TAB 3
with tab3:
    st.subheader("Seasonality index by category (1.0 = average month)")
    h = hist[hist.region.isin(regions) & hist.category.isin(cats)].copy()
    h["m"] = h.month.dt.month
    si = h.groupby(["category", "m"]).demand.mean()
    si = (si / si.groupby(level=0).transform("mean")).reset_index()
    si["Month"] = pd.to_datetime(si.m, format="%m").dt.strftime("%b")
    fig = px.line(si, x="Month", y="demand", color="category", markers=True, labels={"demand": "Index"})
    fig.add_vrect(x0="Mar", x1="Jun", fillcolor="orange", opacity=0.1, annotation_text="Summer peak")
    fig.add_vrect(x0="Oct", x1="Nov", fillcolor="green", opacity=0.1, annotation_text="Festive")
    st.plotly_chart(fig.update_layout(height=380), width="stretch")

    st.subheader("Model backtest – trained on 2023-24, tested on 2025")
    b = bt[bt.region.isin(regions) & bt.category.isin(cats)]
    models = ["Seasonal Naive", "Seasonal Index + Trend", "Holt-Winters", "Ensemble"]
    w = {m: (b.actual - b[m]).abs().sum() / b.actual.sum() for m in models}
    cols = st.columns(4)
    for col, m in zip(cols, models):
        col.metric(m + (" ⭐" if m == "Ensemble" else ""), f"{w[m]:.1%} WAPE",
                   f"{(w['Seasonal Naive'] - w[m]) * 100:+.1f} pp vs naive" if m != "Seasonal Naive" else "baseline",
                   delta_color="normal")
    st.caption("WAPE = Σ|actual − forecast| / Σ actual. Ensemble (production model) was fixed before testing. "
               "Holt-Winters over-extrapolates the 2024 heatwave because only two seasonal cycles exist for training.")

    c1, c2 = st.columns([1, 3])
    with c1:
        sel_r = st.selectbox("Region", regions, key="fr")
        sel_c = st.selectbox("Category", cats, key="fc")
    with c2:
        hh = hist[(hist.region == sel_r) & (hist.category == sel_c)]
        bb = bt[(bt.region == sel_r) & (bt.category == sel_c)]
        ff = fc[(fc.region == sel_r) & (fc.category == sel_c)]
        fig = go.Figure()
        fig.add_scatter(x=hh.month, y=hh.demand, name="Actual demand", line=dict(color="#1F3A5F", width=3))
        fig.add_scatter(x=bb.month, y=bb.Ensemble, name="Backtest (2025)", line=dict(color="#E8833A", dash="dot"))
        fig.add_scatter(x=ff.month, y=ff.upper_80, line=dict(width=0), showlegend=False, hoverinfo="skip")
        fig.add_scatter(x=ff.month, y=ff.lower_80, fill="tonexty", fillcolor="rgba(46,139,87,0.2)",
                        line=dict(width=0), name="80% interval")
        fig.add_scatter(x=ff.month, y=ff.forecast_units, name="Forecast 2026", line=dict(color="seagreen", width=3))
        fig.update_layout(title=f"{sel_c} – {sel_r}: demand, backtest & 2026 forecast (units)", height=400,
                          legend=dict(orientation="h", y=1.12))
        st.plotly_chart(fig, width="stretch")

# ================================================================== TAB 4
with tab4:
    s = sim[sim.region.isin(regions) & sim.category.isin(cats)]
    st.subheader("What if 2025 stock had been planned with the forecast? (SKU × region simulation)")
    lost_a, lost_b = s.lost_units_actual.sum(), s.lost_units_forecast.sum()
    val_a, val_b = s.avg_stock_value_actual.sum(), s.avg_stock_value_forecast.sum()
    dem = s.demand_2025.sum()
    c1, c2, c3 = st.columns(3)
    c1.metric("Lost sales (units)", f"{lost_b:,.0f}", f"{lost_b - lost_a:+,.0f} vs actual", delta_color="inverse")
    c2.metric("Avg capital in stock", cr(val_b), f"{(val_b - val_a) / 1e7:+,.2f} Cr vs actual", delta_color="inverse")
    c3.metric("Fill rate", f"{1 - lost_b / dem:.1%}", f"{((1 - lost_b / dem) - (1 - lost_a / dem)) * 100:+.1f} pp")
    st.caption("Simulation replays actual 2025 demand under an order-up-to policy (forecast + safety stock). "
               "Baseline = what actually happened with last-year-based planning. Synthetic data – illustrative.")

    st.subheader("Inventory health history")
    fi = inv[inv.region.isin(regions) & inv.category.isin(cats) & (inv.month.dt.year == year)]
    c1, c2 = st.columns(2)
    with c1:
        stt = fi.groupby(["month", "stock_status"]).size().reset_index(name="sku_months")
        st.plotly_chart(px.bar(stt, x="month", y="sku_months", color="stock_status",
                               color_discrete_map={"Healthy": "#63BE7B", "Overstock": "#E8833A", "Stock-out": "#D9534F"},
                               title=f"SKU-region status by month – {year}").update_layout(height=360),
                        width="stretch")
    with c2:
        ov = fi.groupby("category").agg(stock_value=("stock_value", "mean"), lost=("lost_revenue_est", "sum")).reset_index()
        fig = go.Figure()
        fig.add_bar(x=ov.category, y=ov.stock_value / 1e7, name="Avg stock value (₹ Cr)", marker_color="#E8833A")
        fig.add_bar(x=ov.category, y=ov.lost / 1e7, name="Lost revenue (₹ Cr)", marker_color="#D9534F")
        fig.update_layout(barmode="group", title=f"Capital locked vs revenue lost – {year}", height=360,
                          legend=dict(orientation="h", y=1.12))
        st.plotly_chart(fig, width="stretch")

    st.subheader("2026 stocking plan")
    service = st.slider("Target service level", 0.80, 0.99, 0.95, 0.01)
    from scipy.stats import norm  # noqa: E402
    z = norm.ppf(service)
    err = acc[acc.model == "Ensemble"].set_index(["region", "category"]).wape
    p = plan[plan.region.isin(regions) & plan.category.isin(cats)].copy()
    p["error_pct"] = [err.loc[(r, c)] for r, c in zip(p.region, p.category)]
    p["safety_stock"] = (z * p.error_pct * p.forecast_units).round()
    p["order_up_to"] = p.forecast_units + p.safety_stock
    pv = p.pivot_table(index=["region", "category"], columns=p.month.dt.strftime("%b"),
                       values="order_up_to", aggfunc="sum")[[m for m in
                       ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]]]
    st.dataframe(pv.style.format("{:,.0f}").background_gradient(axis=1, cmap="Oranges"), width="stretch")
    st.caption(f"Order-up-to level = forecast + z({service:.0%}) = {z:.2f} × forecast error % × forecast. "
               "Build stock from February for the March–June peak; run down from July to avoid post-season overstock.")
    st.download_button("⬇️ Download 2026 plan (CSV)", p.to_csv(index=False), "stocking_plan_2026.csv", "text/csv")
