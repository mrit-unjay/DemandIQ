"""Run the whole pipeline end to end:  python python/run_pipeline.py"""
import runpy
from pathlib import Path

HERE = Path(__file__).resolve().parent
for step in ["01_generate_data.py", "02_clean_and_load_sql.py",
             "03_forecast_and_inventory.py", "04_build_excel_report.py"]:
    print(f"\n=== {step} ===")
    runpy.run_path(str(HERE / step), run_name="__main__")
print("\nDone. Launch the app with:  streamlit run app/streamlit_app.py")
