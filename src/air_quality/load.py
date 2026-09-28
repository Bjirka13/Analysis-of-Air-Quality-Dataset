from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

from .aqi import calculate_daily_aqi


def load_to_duckdb(
    data: pd.DataFrame,
    quality_summary: pd.DataFrame,
    warehouse_path: Path,
    source_file_count: int,
    dropped_empty_measurement_rows: int,
    daily_aqi_data: pd.DataFrame | None = None,
) -> None:
    warehouse_path.parent.mkdir(parents=True, exist_ok=True)
    run_started_at = datetime.now(timezone.utc)
    if daily_aqi_data is None:
        daily_aqi_data = calculate_daily_aqi(data)
    schema_path = Path(__file__).resolve().parents[2] / "sql" / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")

    with duckdb.connect(str(warehouse_path)) as connection:
        connection.register("curated_data", data)
        connection.register("quality_data", quality_summary)
        connection.register("daily_aqi_data", daily_aqi_data)
        connection.execute("BEGIN TRANSACTION")
        try:
            connection.execute(schema_sql)
            connection.execute("DELETE FROM fact_air_quality")
            connection.execute(
                """
                INSERT INTO fact_air_quality (
                    station, observed_at, source_file, source_no,
                    "PM2.5", "PM10", SO2, NO2, CO, O3, TEMP, PRES, DEWP, RAIN, wd, WSPM
                )
                SELECT station, observed_at, source_file, source_no,
                       "PM2.5", "PM10", SO2, NO2, CO, O3, TEMP, PRES, DEWP, RAIN, wd, WSPM
                FROM curated_data
                ORDER BY station, observed_at
                """
            )
            connection.execute("DELETE FROM dim_station")
            connection.execute(
                "INSERT INTO dim_station SELECT DISTINCT station FROM curated_data"
            )
            connection.execute("DELETE FROM data_quality_summary")
            connection.execute(
                "INSERT INTO data_quality_summary SELECT * FROM quality_data"
            )
            connection.execute("DELETE FROM daily_air_quality_aqi")
            connection.execute(
                "INSERT INTO daily_air_quality_aqi SELECT * FROM daily_aqi_data"
            )
            connection.execute(
                """
                ALTER TABLE etl_run_history
                ADD COLUMN IF NOT EXISTS dropped_empty_measurement_rows BIGINT DEFAULT 0
                """
            )
            connection.execute(
                """
                INSERT INTO etl_run_history (
                    run_started_at, source_file_count, station_count, row_count,
                    min_observed_at, max_observed_at, dropped_empty_measurement_rows
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    run_started_at,
                    source_file_count,
                    int(data["station"].nunique()),
                    len(data),
                    data["observed_at"].min().to_pydatetime(),
                    data["observed_at"].max().to_pydatetime(),
                    dropped_empty_measurement_rows,
                ],
            )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.unregister("curated_data")
            connection.unregister("quality_data")
            connection.unregister("daily_aqi_data")