from typing import cast

import pandas as pd

from .constants import POLLUTANT_COLUMNS


def _safe_mode(series: pd.Series) -> str | None:
    non_null = series.dropna()
    if non_null.empty:
        return None
    modes = non_null.mode()
    if modes.empty:
        return None

    mode = modes.iloc[0]
    if not isinstance(mode, str):
        raise TypeError("Wind-direction mode must be a string")
    return mode


def impute_missing_values(data: pd.DataFrame) -> pd.DataFrame:
    imputed = data.copy()
    hour_of_day = imputed["observed_at"].dt.hour

    for column in [*POLLUTANT_COLUMNS, *["TEMP", "PRES", "DEWP", "RAIN", "WSPM"]]:
        station_hour_median = imputed.groupby(["station", hour_of_day], dropna=False)[
            column
        ].transform(lambda values: values.fillna(values.median()))
        imputed[column] = imputed[column].fillna(station_hour_median)

        if imputed[column].isna().any():
            station_median = imputed.groupby("station", dropna=False)[column].transform(
                "median"
            )
            imputed[column] = imputed[column].fillna(station_median)

        if imputed[column].isna().any():
            imputed[column] = imputed[column].fillna(imputed[column].median())

    station_hour_wd_mode = cast(
        pd.Series,
        imputed.groupby(["station", hour_of_day], dropna=False)["wd"].transform(
            _safe_mode
        ),
    )
    imputed["wd"] = imputed["wd"].fillna(station_hour_wd_mode)

    if imputed["wd"].isna().any():
        station_wd_mode = cast(
            pd.Series,
            imputed.groupby("station", dropna=False)["wd"].transform(_safe_mode),
        )
        imputed["wd"] = imputed["wd"].fillna(station_wd_mode)

    if imputed["wd"].isna().any():
        overall_mode = _safe_mode(imputed["wd"])
        if overall_mode is not None:
            imputed["wd"] = imputed["wd"].fillna(overall_mode)

    return imputed