# Power BI Build Guide

This guide rebuilds the 4-page Power BI report from the project's CSVs in about 2–3 hours. Every measure is in `dax_measures.dax`; the colour theme is `voltas_theme.json`.

## 1. Load the data

Run the pipeline first (`python python/run_pipeline.py`), then in Power BI Desktop choose **Get Data → Text/CSV** and load these files from `data/`:

| File | Role |
|---|---|
| `fact_sales.csv` | Cleaned invoice-level sales (fact) |
| `fact_targets.csv` | Monthly region × category targets (fact) |
| `fact_inventory.csv` | Monthly SKU × region stock (fact) |
| `forecast_2026.csv`, `forecast_backtest.csv`, `model_accuracy.csv`, `policy_simulation.csv` | Python model outputs |
| `dim_calendar.csv`, `dim_product.csv`, `dim_dealer.csv`, `dim_distributor.csv` | Dimensions |
| `dim_month.csv`, `dim_region.csv`, `dim_category.csv` | Conformed bridge dimensions |

Alternatively connect to the SQL database directly (SQLite via ODBC, or MySQL/PostgreSQL if you loaded there with `DB_URL`) and import the views `vw_sales_enriched`, `vw_target_achievement`, `vw_inventory_health`.

**Power Query steps worth showing in interviews:** set `invoice_date`, `month` and `date` to Date type; set revenue columns to Fixed Decimal; in `dim_calendar` add a sort column so `month_name` sorts by `month_num` (Column tools → Sort by column); mark `dim_calendar` as the date table (Table tools → Mark as date table).

## 2. Model (star schema)

| From (1) | To (*) |
|---|---|
| `dim_calendar[date]` | `fact_sales[invoice_date]` |
| `dim_product[product_id]` | `fact_sales[product_id]`, `fact_inventory[product_id]` |
| `dim_dealer[dealer_id]` | `fact_sales[dealer_id]` |
| `dim_distributor[distributor_id]` | `dim_dealer[distributor_id]` |
| `dim_month[month]` | `fact_targets[month]`, `fact_inventory[month]`, `forecast_2026[month]`, `forecast_backtest[month]` |
| `dim_region[region]` | `dim_dealer[region]`, `fact_targets[region]`, `fact_inventory[region]`, `forecast_2026[region]`, `forecast_backtest[region]`, `policy_simulation[region]` |
| `dim_category[category]` | `dim_product[category]`, `fact_targets[category]`, `forecast_2026[category]`, `forecast_backtest[category]`, `policy_simulation[category]` |

Also relate `dim_month[month]` to `dim_calendar[month_start]` (one month → many dates) so that a single Year/Month slicer filters both sales and targets. All filters single-direction. Use `dim_region` and `dim_category` (not the columns on the fact tables) in every slicer, so one slicer filters sales, targets, inventory and forecasts together.

Create the what-if parameter: **Modeling → New parameter → Numeric range**, name `Service Level`, 0.80 to 0.99, increment 0.01, default 0.95.

## 3. Report pages

**Theme:** View → Themes → Browse → `voltas_theme.json`.
**Slicers on every page (sync slicers):** Year, Region (`dim_region`), Category (`dim_category`).

### Page 1 – Executive Overview
KPI cards for Net Revenue Cr, Revenue YoY %, Target Achievement %, Gross Margin %, Active Dealers. A combo chart of Net Revenue (columns) and Target Revenue (line) by month. A matrix of region × category showing Target Achievement %, with conditional background from `Target Status Colour` (Format → Cell elements → Background colour → Field value). A donut of revenue by region, and a smart narrative or text box with 3 insights.

### Page 2 – Channel Performance
A distributor table with Net Revenue Cr, Revenue YoY %, Gross Margin %, Active Dealers and Avg Discount %, plus data bars. A dealer table with Dealer Rank, Revenue Share % and Pareto Cumulative %, filtered to the top 20 with a Top N filter. A Pareto line + column chart of dealers sorted by revenue against Pareto Cumulative %, with a constant line at 80%. A Declining Dealers card, a scatter of Avg Discount % versus Gross Margin % by category with season in the legend, and a decomposition tree of Net Revenue → Region → Distributor → Dealer tier → Dealer.

### Page 3 – Seasonality & Forecast
A line chart of Seasonality Index by month_name with category in the legend. Cards for WAPE Naive, WAPE Ensemble and Forecast Accuracy Gain pp. A line chart of `dim_month[month]` against Backtest Actual, Backtest Ensemble and Backtest Naive for 2025. A 2026 forecast line chart showing Forecast Units with Forecast Lower 80 and Forecast Upper 80 (as an error band: Analytics pane → Error bars, or two lines). A table of model_accuracy filtered to the Ensemble model, conditional-formatted by WAPE.

### Page 4 – Inventory Planning
Cards for Fill Rate %, Lost Revenue Est, Stock Value and Days of Cover. A stacked column of Stock-out SKU Months versus Overstock SKU Months by month. Simulation cards for Sim Lost Reduction %, Sim Capital Released Cr, and Sim Stock Value Actual Cr vs Forecast Cr. The Service Level slicer (what-if parameter) feeds a matrix of region × category by month showing Order Up To Level, with a heatmap. A drill-through page on SKU from any visual shows that SKU's monthly opening, receipts, sold, lost and closing values.

## 4. Finishing touches

Add bookmarks for "Peak season view" (Mar–Jun filter) and "Full year". Add tooltips pages showing the month's YoY and target status on hover. Set up **Row-level security** with a role per region (`dim_region[region] = "North"`) to show you understand regional sales-manager access. Then publish to Power BI Service (free workspace) and take screenshots for your GitHub README.
