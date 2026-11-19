"""
Step 2 - Clean raw sales data and load the star schema into a SQL database.

Default: SQLite (zero setup, file at ../data/voltas_dw.db).
To use MySQL / PostgreSQL instead, set DB_URL, e.g.
    DB_URL="postgresql+psycopg2://user:pass@localhost:5432/voltas"
    DB_URL="mysql+pymysql://user:pass@localhost:3306/voltas"
"""
import os
import sqlite3
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA, SQL = ROOT / "data", ROOT / "sql"
DB_PATH = DATA / "voltas_dw.db"


def clean_sales(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    log = {"raw_rows": len(raw)}
    df = raw.drop_duplicates()
    log["duplicates_removed"] = log["raw_rows"] - len(df)

    n = len(df)
    df = df.dropna(subset=["units"])
    log["null_units_removed"] = n - len(df)

    n = len(df)
    df = df[df["net_revenue"] > 0]
    log["invalid_revenue_removed"] = n - len(df)

    df["invoice_date"] = pd.to_datetime(df["invoice_date"]).dt.date
    df["units"] = df["units"].astype(int)
    df["gross_margin"] = df["net_revenue"] - df["cogs"]
    log["clean_rows"] = len(df)
    return df, log


def main():
    raw = pd.read_csv(DATA / "fact_sales_raw.csv")
    sales, log = clean_sales(raw)
    for k, v in log.items():
        print(f"  {k:24s} {v:>8,}")
    sales.to_csv(DATA / "fact_sales.csv", index=False)

    tables = {
        "dim_product": pd.read_csv(DATA / "dim_product.csv"),
        "dim_distributor": pd.read_csv(DATA / "dim_distributor.csv"),
        "dim_dealer": pd.read_csv(DATA / "dim_dealer.csv"),
        "dim_calendar": pd.read_csv(DATA / "dim_calendar.csv"),
        "fact_sales": sales,
        "fact_inventory": pd.read_csv(DATA / "fact_inventory.csv"),
        "fact_targets": pd.read_csv(DATA / "fact_targets.csv"),
    }

    # conformed dimensions for Power BI (one slicer filters sales, targets, inventory, forecasts)
    pd.DataFrame({"month": pd.date_range("2023-01-01", "2026-12-01", freq="MS").date}).to_csv(DATA / "dim_month.csv", index=False)
    pd.DataFrame({"region": ["North", "West", "South", "East"]}).to_csv(DATA / "dim_region.csv", index=False)
    pd.DataFrame({"category": sorted(tables["dim_product"]["category"].unique())}).to_csv(DATA / "dim_category.csv", index=False)

    db_url = os.getenv("DB_URL")
    if db_url:  # MySQL / Postgres via SQLAlchemy
        from sqlalchemy import create_engine
        engine = create_engine(db_url)
        for name, df in tables.items():
            df.to_sql(name, engine, if_exists="replace", index=False)
        print(f"Loaded into {db_url.split('@')[-1]}")
        return

    DB_PATH.unlink(missing_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript((SQL / "01_schema.sql").read_text())
    for name, df in tables.items():
        df.to_sql(name, con, if_exists="append", index=False)
        print(f"  loaded {name:16s} {len(df):>8,}")
    con.executescript((SQL / "03_views.sql").read_text())
    con.commit()
    con.close()
    print(f"SQLite warehouse ready: {DB_PATH}")


if __name__ == "__main__":
    main()
