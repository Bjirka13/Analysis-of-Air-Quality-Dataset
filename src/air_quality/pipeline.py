from pathlib import Path

from .aqi import calculate_daily_aqi
from .constants import MEASUREMENT_COLUMNS
from .extract import extract_raw_data
from .load import load_to_duckdb
from .quality import build_quality_summary
from .transform import transform_data


def run_pipeline(raw_dir: Path, warehouse_path: Path) -> dict[str, object]:
    raw_data = extract_raw_data(raw_dir)
    dropped_empty_measurement_rows = int(
        raw_data[MEASUREMENT_COLUMNS].isna().all(axis=1).sum()
    )
    curated_data = transform_data(raw_data)
    quality_summary = build_quality_summary(curated_data)
    daily_aqi = calculate_daily_aqi(curated_data)
    load_to_duckdb(
        curated_data,
        quality_summary,
        warehouse_path,
        source_file_count=raw_data["source_file"].nunique(),
        dropped_empty_measurement_rows=dropped_empty_measurement_rows,
        daily_aqi_data=daily_aqi,
    )

    return {
        "source_files": int(raw_data["source_file"].nunique()),
        "stations": int(curated_data["station"].nunique()),
        "rows": len(curated_data),
        "dropped_empty_measurement_rows": dropped_empty_measurement_rows,
        "missing_measurement_rows": int(
            curated_data[MEASUREMENT_COLUMNS].isna().any(axis=1).sum()
        ),
        "aqi_days": len(daily_aqi),
        "aqi_valid_days": int(daily_aqi["aqi"].notna().sum()),
        "warehouse": str(warehouse_path),
    }