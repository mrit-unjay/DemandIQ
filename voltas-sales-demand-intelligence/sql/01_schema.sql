-- =====================================================================
-- Voltas Sales, Channel & Demand Intelligence - Star Schema
-- Written in portable SQL (runs on SQLite; minor type tweaks for MySQL/Postgres)
-- =====================================================================

DROP TABLE IF EXISTS fact_sales;
DROP TABLE IF EXISTS fact_inventory;
DROP TABLE IF EXISTS fact_targets;
DROP TABLE IF EXISTS dim_dealer;
DROP TABLE IF EXISTS dim_distributor;
DROP TABLE IF EXISTS dim_product;
DROP TABLE IF EXISTS dim_calendar;

CREATE TABLE dim_product (
    product_id   INTEGER PRIMARY KEY,
    sku          VARCHAR(20) NOT NULL UNIQUE,
    category     VARCHAR(30) NOT NULL,      -- Split AC, Window AC, Air Cooler, ...
    model_name   VARCHAR(80),
    capacity     VARCHAR(20),
    list_price   DECIMAL(12,2),
    unit_cost    DECIMAL(12,2)
);

CREATE TABLE dim_distributor (
    distributor_id    INTEGER PRIMARY KEY,
    distributor_name  VARCHAR(80),
    region            VARCHAR(20),
    state             VARCHAR(40),
    onboarded_date    DATE,
    credit_limit_lakh INTEGER
);

CREATE TABLE dim_dealer (
    dealer_id      INTEGER PRIMARY KEY,
    dealer_name    VARCHAR(80),
    distributor_id INTEGER REFERENCES dim_distributor(distributor_id),
    region         VARCHAR(20),
    state          VARCHAR(40),
    city_tier      VARCHAR(10),            -- Metro / Tier 1 / Tier 2 / Tier 3
    dealer_tier    VARCHAR(10)             -- Platinum / Gold / Silver
);

CREATE TABLE dim_calendar (
    date         DATE PRIMARY KEY,
    year         INTEGER,
    quarter      VARCHAR(2),
    month_num    INTEGER,
    month_name   VARCHAR(3),
    month_start  DATE,
    fiscal_year  VARCHAR(4),               -- Indian FY (Apr-Mar)
    season       VARCHAR(20)               -- Summer (Peak) / Monsoon / Festive / Winter
);

CREATE TABLE fact_sales (
    invoice_id     VARCHAR(15),
    invoice_date   DATE REFERENCES dim_calendar(date),
    dealer_id      INTEGER REFERENCES dim_dealer(dealer_id),
    distributor_id INTEGER REFERENCES dim_distributor(distributor_id),
    product_id     INTEGER REFERENCES dim_product(product_id),
    units          INTEGER,
    gross_revenue  DECIMAL(14,2),
    discount_pct   DECIMAL(6,4),
    net_revenue    DECIMAL(14,2),
    cogs           DECIMAL(14,2),
    gross_margin   DECIMAL(14,2)
);

CREATE TABLE fact_inventory (
    month            DATE,
    region           VARCHAR(20),
    product_id       INTEGER REFERENCES dim_product(product_id),
    opening_stock    INTEGER,
    receipts         INTEGER,
    units_sold       INTEGER,
    lost_sales_units INTEGER,              -- demand not served due to stock-out
    closing_stock    INTEGER
);

CREATE TABLE fact_targets (
    month          DATE,
    region         VARCHAR(20),
    category       VARCHAR(30),
    target_revenue DECIMAL(14,2)
);

CREATE INDEX ix_sales_date    ON fact_sales(invoice_date);
CREATE INDEX ix_sales_dealer  ON fact_sales(dealer_id);
CREATE INDEX ix_sales_product ON fact_sales(product_id);
CREATE INDEX ix_inv_month     ON fact_inventory(month, region, product_id);
