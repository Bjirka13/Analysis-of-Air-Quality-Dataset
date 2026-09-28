import pandas as pd

from .constants import MEASUREMENT_COLUMNS, POLLUTANT_COLUMNS, WIND_DIRECTIONS


def transform_data(raw_data: pd.DataFrame) -> pd.DataFrame:
    data = raw_data.copy()
    data["observed_at"] = pd.to_datetime(
        data[["year", "month", "day", "hour"]], errors="coerce"
    )
    if data["observed_at"].isna().any():
        raise ValueError("Source data contains invalid date or time values")

    data["source_no"] = pd.to_numeric(data["No"], errors="coerce")
    if data["source_no"].isna().any():
        raise ValueError("Source data contains invalid row identifiers in 'No'")

    empty_measurement_rows = data[MEASUREMENT_COLUMNS].isna().all(axis=1)
    data = data.loc[~empty_measurement_rows].copy()
    if data.empty:
        raise ValueError("No records remain after removing rows with all measurements missing")

    duplicated_keys = data.duplicated(["station", "observed_at"])
    if duplicated_keys.any():
        examples = data.loc[duplicated_keys, ["station", "observed_at"]].head(3)
        raise ValueError(f"Duplicate station/timestamp keys found:\n{examples}")

    numeric_pollutants = data[POLLUTANT_COLUMNS]
    if (numeric_pollutants.lt(0).fillna(False)).any().any():
        raise ValueError("Pollutant concentrations must not be negative")

    unexpected_wind_directions = set(data["wd"].dropna().unique()) - WIND_DIRECTIONS
    if unexpected_wind_directions:
        raise ValueError(
            f"Unexpected wind direction values: {sorted(unexpected_wind_directions)}"
        )

    return (
        data[["station", "observed_at", "source_file", "source_no", *MEASUREMENT_COLUMNS]]
        .sort_values(["station", "observed_at"])
        .reset_index(drop=True)
    )