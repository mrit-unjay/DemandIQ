-- =====================================================================
-- Business questions answered in SQL
-- (CTEs, window functions, CASE logic, NULL handling)
-- =====================================================================

-- Q1. Headline KPIs by year: revenue (Cr), units, margin %, avg discount
SELECT  year,
        ROUND(SUM(net_revenue) / 1e7, 2)                   AS revenue_cr,
        SUM(units)                                         AS units,
        ROUND(SUM(gross_margin) * 100.0 / SUM(net_revenue), 1) AS gross_margin_pct,
        ROUND(AVG(discount_pct) * 100, 2)                  AS avg_discount_pct
FROM vw_sales_enriched
GROUP BY year
ORDER BY year;


-- Q2. Year-on-year growth by category (LAG)
WITH yearly AS (
    SELECT category, year, SUM(net_revenue) AS revenue
    FROM vw_sales_enriched
    GROUP BY category, year
)
SELECT  category, year,
        ROUND(revenue / 1e7, 2) AS revenue_cr,
        ROUND((revenue - LAG(revenue) OVER (PARTITION BY category ORDER BY year)) * 100.0
              / LAG(revenue) OVER (PARTITION BY category ORDER BY year), 1) AS yoy_growth_pct
FROM yearly
ORDER BY category, year;


-- Q3. Seasonality index by category & month  (month avg / overall monthly avg)
WITH monthly AS (
    SELECT category, year, month_num, SUM(units) AS units
    FROM vw_sales_enriched
    GROUP BY category, year, month_num
),
avg_by_month AS (
    SELECT category, month_num, AVG(units) AS avg_units
    FROM monthly GROUP BY category, month_num
)
SELECT  category, month_num,
        ROUND(avg_units / AVG(avg_units) OVER (PARTITION BY category), 2) AS seasonality_index
FROM avg_by_month
ORDER BY category, month_num;


-- Q4. Region x category target achievement for latest fiscal year, with status band
SELECT  region, category,
        ROUND(SUM(target_revenue) / 1e7, 2) AS target_cr,
        ROUND(SUM(actual_revenue) / 1e7, 2) AS actual_cr,
        ROUND(SUM(actual_revenue) * 100.0 / SUM(target_revenue), 1) AS achievement_pct,
        CASE WHEN SUM(actual_revenue) >= SUM(target_revenue)        THEN 'Achieved'
             WHEN SUM(actual_revenue) >= 0.9 * SUM(target_revenue)  THEN 'Near (90-100%)'
             ELSE 'Missed (<90%)' END AS status
FROM vw_target_achievement
WHERE month >= '2025-01-01'
GROUP BY region, category
ORDER BY achievement_pct;


-- Q5. Top 3 dealers per region by 2025 revenue (ROW_NUMBER)
WITH dealer_rev AS (
    SELECT region, dealer_name, dealer_tier, SUM(net_revenue) AS revenue
    FROM vw_sales_enriched
    WHERE year = 2025
    GROUP BY region, dealer_name, dealer_tier
),
ranked AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY region ORDER BY revenue DESC) AS rn
    FROM dealer_rev
)
SELECT region, rn AS rank_in_region, dealer_name, dealer_tier, ROUND(revenue / 1e5, 1) AS revenue_lakh
FROM ranked WHERE rn <= 3
ORDER BY region, rn;


-- Q6. Distributor scorecard: revenue, growth, margin, active dealers, revenue share
WITH d AS (
    SELECT distributor_name, region,
           SUM(CASE WHEN year = 2025 THEN net_revenue END) AS rev_2025,
           SUM(CASE WHEN year = 2024 THEN net_revenue END) AS rev_2024,
           SUM(CASE WHEN year = 2025 THEN gross_margin END) AS gm_2025,
           COUNT(DISTINCT CASE WHEN year = 2025 THEN dealer_id END) AS active_dealers
    FROM vw_sales_enriched
    GROUP BY distributor_name, region
)
SELECT  distributor_name, region, active_dealers,
        ROUND(rev_2025 / 1e7, 2) AS rev_2025_cr,
        ROUND((rev_2025 - rev_2024) * 100.0 / rev_2024, 1) AS yoy_pct,
        ROUND(gm_2025 * 100.0 / rev_2025, 1) AS gm_pct,
        ROUND(rev_2025 * 100.0 / SUM(rev_2025) OVER (), 2) AS share_of_total_pct
FROM d
ORDER BY rev_2025 DESC;


-- Q7. Dealer Pareto: how many dealers make 80% of revenue? (running total)
WITH dr AS (
    SELECT dealer_id, SUM(net_revenue) AS revenue
    FROM vw_sales_enriched WHERE year = 2025 GROUP BY dealer_id
),
cum AS (
    SELECT dealer_id, revenue,
           SUM(revenue) OVER (ORDER BY revenue DESC ROWS UNBOUNDED PRECEDING) * 1.0
             / SUM(revenue) OVER () AS cum_share,
           ROW_NUMBER() OVER (ORDER BY revenue DESC) AS rn,
           COUNT(*) OVER () AS total_dealers
    FROM dr
)
SELECT MIN(rn) AS dealers_for_80pct, MAX(total_dealers) AS total_dealers,
       ROUND(MIN(rn) * 100.0 / MAX(total_dealers), 1) AS pct_of_dealers
FROM cum WHERE cum_share >= 0.8;


-- Q8. Declining dealers: 2025 H1 revenue down >20% vs 2024 H1 (early-warning list)
WITH h AS (
    SELECT dealer_name, region, distributor_name,
           SUM(CASE WHEN invoice_date BETWEEN '2024-01-01' AND '2024-06-30' THEN net_revenue ELSE 0 END) AS h1_2024,
           SUM(CASE WHEN invoice_date BETWEEN '2025-01-01' AND '2025-06-30' THEN net_revenue ELSE 0 END) AS h1_2025
    FROM vw_sales_enriched
    GROUP BY dealer_name, region, distributor_name
)
SELECT *, ROUND((h1_2025 - h1_2024) * 100.0 / h1_2024, 1) AS change_pct
FROM h
WHERE h1_2024 > 0 AND h1_2025 < 0.8 * h1_2024
ORDER BY change_pct;


-- Q9. Stock-outs during peak season: lost revenue by region & category
SELECT  region, category,
        SUM(lost_sales_units)                 AS lost_units,
        ROUND(SUM(lost_revenue_est) / 1e5, 1) AS lost_revenue_lakh,
        COUNT(CASE WHEN stock_status = 'Stock-out' THEN 1 END) AS stockout_sku_months
FROM vw_inventory_health
WHERE CAST(SUBSTR(month, 6, 2) AS INTEGER) BETWEEN 3 AND 6
GROUP BY region, category
ORDER BY lost_revenue_lakh DESC;


-- Q10. Overstock capital locked after peak season (Jul-Sep closing stock value)
SELECT  region, category,
        ROUND(AVG(days_of_cover), 0)         AS avg_days_of_cover,
        ROUND(SUM(stock_value) / 1e5, 1)     AS stock_value_lakh
FROM vw_inventory_health
WHERE CAST(SUBSTR(month, 6, 2) AS INTEGER) BETWEEN 7 AND 9
  AND stock_status = 'Overstock'
GROUP BY region, category
ORDER BY stock_value_lakh DESC;


-- Q11. 3-month moving average of units by category (trend smoothing)
WITH m AS (
    SELECT month, category, SUM(units) AS units
    FROM vw_sales_enriched GROUP BY month, category
)
SELECT  month, category, units,
        ROUND(AVG(units) OVER (PARTITION BY category ORDER BY month
                               ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 0) AS units_3m_ma
FROM m
ORDER BY category, month;


-- Q12. Discount effectiveness: discount band vs units per invoice & margin
SELECT  CASE WHEN discount_pct < 0.03 THEN '0-3%'
             WHEN discount_pct < 0.06 THEN '3-6%'
             WHEN discount_pct < 0.10 THEN '6-10%'
             ELSE '10%+' END AS discount_band,
        season,
        COUNT(*)                                         AS invoices,
        ROUND(AVG(units), 2)                             AS avg_units_per_invoice,
        ROUND(SUM(gross_margin) * 100.0 / SUM(net_revenue), 1) AS gm_pct
FROM vw_sales_enriched
GROUP BY discount_band, season
ORDER BY season, discount_band;
