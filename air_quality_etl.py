import argparse
import json
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from air_quality import (
    MEASUREMENT_COLUMNS,
    POLLUTANT_COLUMNS,
    RAW_COLUMNS,
    WEATHER_COLUMNS,
    WIND_DIRECTIONS,
    build_quality_summary,
    calculate_daily_aqi,
    extract_raw_data,
    impute_missing_values,
    load_to_duckdb,
    run_pipeline,
    transform_data,
)

__all__ = [
    "MEASUREMENT_COLUMNS",
    "POLLUTANT_COLUMNS",
    "RAW_COLUMNS",
    "WEATHER_COLUMNS",
    "WIND_DIRECTIONS",
    "build_quality_summary",
    "calculate_daily_aqi",
    "extract_raw_data",
    "impute_missing_values",
    "load_to_duckdb",
    "run_pipeline",
    "transform_data",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the air quality DuckDB warehouse")
    parser.add_argument(
        "--config", type=Path, default=PROJECT_ROOT / "configs" / "pipeline.yaml"
    )
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument(
        "--warehouse",
        type=Path,
    )
    args = parser.parse_args()

    from dotenv import load_dotenv
    import yaml

    load_dotenv(PROJECT_ROOT / ".env")
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))

    raw_dir_value = (
        args.raw_dir
        or os.getenv("AIR_QUALITY_RAW_DIR")
        or config["paths"]["raw_data"]
    )
    warehouse_value = (
        args.warehouse
        or os.getenv("AIR_QUALITY_WAREHOUSE")
        or config["paths"]["warehouse"]
    )
    raw_dir = Path(raw_dir_value)
    warehouse = Path(warehouse_value)
    if not raw_dir.is_absolute():
        raw_dir = PROJECT_ROOT / raw_dir
    if not warehouse.is_absolute():
        warehouse = PROJECT_ROOT / warehouse

    result = run_pipeline(raw_dir, warehouse)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()