-- =====================================================================
-- Reporting views consumed by Python, Streamlit, Excel and Power BI
-- =====================================================================

DROP VIEW IF EXISTS vw_sales_enriched;
CREATE VIEW vw_sales_enriched AS
SELECT  s.invoice_id,
        s.invoice_date,
        SUBSTR(s.invoice_date, 1, 7) || '-01'  AS month,
        c.year, c.month_num, c.fiscal_year, c.season,
        d.region, d.state, d.city_tier, d.dealer_tier,
        d.dealer_id, d.dealer_name,
        di.distributor_id, di.distributor_name,
        p.product_id, p.sku, p.category, p.model_name,
        s.units, s.gross_revenue, s.discount_pct,
        s.net_revenue, s.cogs, s.gross_margin
FROM fact_sales s
JOIN dim_calendar    c  ON c.date = s.invoice_date
JOIN dim_dealer      d  ON d.dealer_id = s.dealer_id
JOIN dim_distributor di ON di.distributor_id = s.distributor_id
JOIN dim_product     p  ON p.product_id = s.product_id;


-- Actual vs Target at Month x Region x Category grain
DROP VIEW IF EXISTS vw_target_achievement;
CREATE VIEW vw_target_achievement AS
WITH actual AS (
    SELECT month, region, category,
           SUM(net_revenue) AS actual_revenue,
           SUM(units)       AS actual_units
    FROM vw_sales_enriched
    GROUP BY month, region, category
)
SELECT  t.month, t.region, t.category,
        t.target_revenue,
        COALESCE(a.actual_revenue, 0)                        AS actual_revenue,
        COALESCE(a.actual_units, 0)                          AS actual_units,
        ROUND(COALESCE(a.actual_revenue, 0) * 1.0 / NULLIF(t.target_revenue, 0), 4) AS achievement_pct
FROM fact_targets t
LEFT JOIN actual a
       ON a.month = t.month AND a.region = t.region AND a.category = t.category;


-- Inventory health: days of cover, stock-out and overstock flags
DROP VIEW IF EXISTS vw_inventory_health;
CREATE VIEW vw_inventory_health AS
SELECT  i.month, i.region, p.category, p.sku, p.model_name,
        i.opening_stock, i.receipts, i.units_sold, i.lost_sales_units, i.closing_stock,
        i.units_sold + i.lost_sales_units                              AS true_demand,
        ROUND(i.closing_stock * 30.0 / NULLIF(i.units_sold, 0), 1)     AS days_of_cover,
        i.lost_sales_units * p.list_price                              AS lost_revenue_est,
        i.closing_stock * p.unit_cost                                  AS stock_value,
        CASE WHEN i.lost_sales_units > 0                                         THEN 'Stock-out'
             WHEN i.closing_stock > 2.0 * NULLIF(i.units_sold, 0)                THEN 'Overstock'
             WHEN i.units_sold = 0 AND i.closing_stock > 0                       THEN 'Overstock'
             ELSE 'Healthy' END                                        AS stock_status
FROM fact_inventory i
JOIN dim_product p ON p.product_id = i.product_id;
