import json

import pandas as pd

from .constants import MEASUREMENT_COLUMNS


def build_quality_summary(data: pd.DataFrame) -> pd.DataFrame:
    summaries: list[dict[str, object]] = []
    for station, group in data.groupby("station", sort=True):
        start = group["observed_at"].min()
        end = group["observed_at"].max()
        expected_hours = len(pd.date_range(start, end, freq="h"))
        null_counts = group[MEASUREMENT_COLUMNS].isna().sum().astype(int).to_dict()

        summaries.append(
            {
                "station": station,
                "row_count": len(group),
                "duplicate_key_count": int(
                    group.duplicated(["station", "observed_at"]).sum()
                ),
                "rows_with_any_missing_measurement": int(
                    group[MEASUREMENT_COLUMNS].isna().any(axis=1).sum()
                ),
                "missing_hours_inside_range": max(
                    expected_hours - group["observed_at"].nunique(), 0
                ),
                "min_observed_at": start,
                "max_observed_at": end,
                "missing_by_column_json": json.dumps(null_counts, sort_keys=True),
            }
        )

    return pd.DataFrame(summaries)