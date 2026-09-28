import json
import tempfile
import unittest
from pathlib import Path

import duckdb
import pandas as pd

from air_quality_etl import (
    MEASUREMENT_COLUMNS,
    build_quality_summary,
    calculate_daily_aqi,
    impute_missing_values,
    load_to_duckdb,
    transform_data,
)


def make_raw_row(row_number: int, hour: int, all_measurements_missing: bool = False):
    values = {
        "No": row_number,
        "year": 2013,
        "month": 3,
        "day": 1,
        "hour": hour,
        "station": "TestStation",
        "source_file": "test.csv",
    }
    values.update(
        {
            column: None if all_measurements_missing else 1
            for column in MEASUREMENT_COLUMNS
        }
    )
    values["wd"] = None if all_measurements_missing else "N"
    return values


class AirQualityETLTests(unittest.TestCase):
    def test_calculates_daily_china_mep_aqi(self):
        rows = [make_raw_row(row_number, hour) for hour, row_number in enumerate(range(24))]
        for row in rows:
            row.update({"PM2.5": 75, "PM10": 50, "SO2": 50, "NO2": 40, "CO": 2000, "O3": 100})

        transformed = transform_data(pd.DataFrame(rows))
        daily_aqi = calculate_daily_aqi(transformed).iloc[0]

        self.assertEqual(daily_aqi["aqi"], 100)
        self.assertEqual(daily_aqi["primary_pollutant"], "PM2.5")
        self.assertEqual(daily_aqi["aqi_category"], "Good")
        self.assertEqual(daily_aqi["co_24h"], 2)

    def test_aqi_library_maximum_is_used_for_extreme_concentrations(self):
        rows = [make_raw_row(row_number, hour) for hour, row_number in enumerate(range(24))]
        for row in rows:
            row.update({"PM2.5": 600, "PM10": 50, "SO2": 50, "NO2": 40, "CO": 2000, "O3": 100})

        daily_aqi = calculate_daily_aqi(transform_data(pd.DataFrame(rows))).iloc[0]

        self.assertEqual(daily_aqi["aqi"], 500)
        self.assertEqual(daily_aqi["iaqi_pm25"], 500)

    def test_daily_aqi_is_null_when_24_hour_coverage_is_insufficient(self):
        rows = [make_raw_row(hour + 1, hour) for hour in range(19)]

        daily_aqi = calculate_daily_aqi(transform_data(pd.DataFrame(rows))).iloc[0]

        self.assertTrue(pd.isna(daily_aqi["aqi"]))
        self.assertEqual(daily_aqi["valid_hours_pm25"], 19)

    def test_drops_only_rows_with_all_measurements_missing(self):
        all_missing = make_raw_row(1, 0, all_measurements_missing=True)
        partial_missing = make_raw_row(2, 1)
        partial_missing["PM2.5"] = None

        transformed = transform_data(pd.DataFrame([all_missing, partial_missing]))

        self.assertEqual(len(transformed), 1)
        self.assertEqual(transformed.loc[0, "source_no"], 2)
        self.assertTrue(pd.isna(transformed.loc[0, "PM2.5"]))

    def test_rejects_duplicate_station_and_timestamp(self):
        first = make_raw_row(1, 0)
        duplicate = make_raw_row(2, 0)

        with self.assertRaisesRegex(ValueError, "Duplicate station/timestamp"):
            transform_data(pd.DataFrame([first, duplicate]))

    def test_rejects_negative_pollutant_values(self):
        row = make_raw_row(1, 0)
        row["PM2.5"] = -1

        with self.assertRaisesRegex(ValueError, "must not be negative"):
            transform_data(pd.DataFrame([row]))

    def test_quality_summary_reports_nulls(self):
        row = make_raw_row(1, 0)
        row["PM2.5"] = None
        transformed = transform_data(pd.DataFrame([row]))

        summary = build_quality_summary(transformed).iloc[0]
        missing_counts = json.loads(summary["missing_by_column_json"])

        self.assertEqual(summary["row_count"], 1)
        self.assertEqual(missing_counts["PM2.5"], 1)
        self.assertEqual(summary["missing_hours_inside_range"], 0)

    def test_partial_missing_values_are_preserved_for_fact_load(self):
        row_1 = make_raw_row(1, 12)
        row_1["PM2.5"] = 15
        row_1["wd"] = "N"

        row_2 = make_raw_row(2, 13)
        row_2["PM2.5"] = 25
        row_2["wd"] = "NE"

        row_3 = make_raw_row(3, 14)
        row_3["PM2.5"] = None
        row_3["wd"] = None

        transformed = transform_data(pd.DataFrame([row_1, row_2, row_3]))

        self.assertTrue(pd.isna(transformed.loc[2, "PM2.5"]))
        self.assertTrue(pd.isna(transformed.loc[2, "wd"]))

        imputed = impute_missing_values(transformed)
        self.assertAlmostEqual(float(imputed.loc[2, "PM2.5"]), 20.0)
        self.assertEqual(imputed.loc[2, "wd"], "N")

    def test_duckdb_load_is_repeatable_and_records_runs(self):
        transformed = transform_data(pd.DataFrame([make_raw_row(1, 0)]))
        summary = build_quality_summary(transformed)

        with tempfile.TemporaryDirectory() as temporary_directory:
            warehouse = Path(temporary_directory) / "air_quality.duckdb"
            for _ in range(2):
                load_to_duckdb(
                    transformed,
                    summary,
                    warehouse,
                    source_file_count=1,
                    dropped_empty_measurement_rows=1,
                )

            with duckdb.connect(str(warehouse), read_only=True) as connection:
                fact_count = connection.execute(
                    "SELECT COUNT(*) FROM fact_air_quality"
                ).fetchone()[0]
                aqi_count = connection.execute(
                    "SELECT COUNT(*) FROM daily_air_quality_aqi"
                ).fetchone()[0]
                run_count, drop_count = connection.execute(
                    """
                    SELECT COUNT(*), SUM(dropped_empty_measurement_rows)
                    FROM etl_run_history
                    """
                ).fetchone()

        self.assertEqual(fact_count, 1)
        self.assertEqual(aqi_count, 1)
        self.assertEqual(run_count, 2)
        self.assertEqual(drop_count, 2)


if __name__ == "__main__":
    unittest.main()