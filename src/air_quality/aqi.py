import aqi as aqi_library
import pandas as pd
from aqi import constants as aqi_pollutants


MIN_VALID_DAILY_HOURS = 20
MIN_VALID_OZONE_8H_HOURS = 6

POLLUTANT_INPUTS = {
    "PM2.5": ("pm25_24h", "pm25", aqi_pollutants.POLLUTANT_PM25),
    "PM10": ("pm10_24h", "pm10", aqi_pollutants.POLLUTANT_PM10),
    "SO2": ("so2_24h", "so2_24h", aqi_pollutants.POLLUTANT_SO2_24H),
    "NO2": ("no2_24h", "no2_24h", aqi_pollutants.POLLUTANT_NO2_24H),
    "CO": ("co_24h", "co_24h", aqi_pollutants.POLLUTANT_CO_24H),
    "O3": ("o3_8h_max", "o3_8h_max", aqi_pollutants.POLLUTANT_O3_8H),
}
DAILY_AVERAGE_POLLUTANTS = ["PM2.5", "PM10", "SO2", "NO2", "CO"]
MAX_MEP_CONCENTRATIONS = {
    "pm25_24h": 500.0,
    "pm10_24h": 600.0,
    "so2_24h": 2620.0,
    "no2_24h": 940.0,
    "co_24h": 60.0,
    "o3_8h_max": 800.0,
}


def _aqi_category(aqi_value: int) -> str:
    if aqi_value <= 50:
        return "Excellent"
    if aqi_value <= 100:
        return "Good"
    if aqi_value <= 150:
        return "Lightly polluted"
    if aqi_value <= 200:
        return "Moderately polluted"
    if aqi_value <= 300:
        return "Heavily polluted"
    return "Severely polluted"


def calculate_daily_aqi(data: pd.DataFrame) -> pd.DataFrame:
    ordered = data.sort_values(["station", "observed_at"]).reset_index(drop=True).copy()
    ordered["o3_8h_avg"] = float("nan")

    for _, station_data in ordered.groupby("station", sort=False):
        rolling_o3 = (
            station_data.set_index("observed_at")["O3"]
            .rolling("8h", closed="right", min_periods=MIN_VALID_OZONE_8H_HOURS)
            .mean()
        )
        ordered.loc[station_data.index, "o3_8h_avg"] = rolling_o3.to_numpy()

    ordered["observed_date"] = ordered["observed_at"].dt.date
    daily_rows: list[dict[str, object]] = []

    for (station, observed_date), group in ordered.groupby(
        ["station", "observed_date"], sort=True
    ):
        valid_hours = {
            column: int(group[column].count())
            for column in [*DAILY_AVERAGE_POLLUTANTS, "O3"]
        }
        concentrations: dict[str, float | None] = {}
        for column in DAILY_AVERAGE_POLLUTANTS:
            concentration_column = f"{column.lower().replace('.', '')}_24h"
            daily_mean = (
                float(group[column].mean())
                if valid_hours[column] >= MIN_VALID_DAILY_HOURS
                else None
            )
            concentrations[concentration_column] = (
                daily_mean / 1000 if column == "CO" and daily_mean is not None else daily_mean
            )
        concentrations["o3_8h_max"] = (
            float(group["o3_8h_avg"].max())
            if group["o3_8h_avg"].notna().any()
            else None
        )

        row: dict[str, object] = {
            "station": station,
            "observed_date": observed_date,
            "aqi": None,
            "primary_pollutant": None,
            "aqi_category": None,
            **concentrations,
            **{
                f"valid_hours_{column.lower().replace('.', '')}": valid_hours[column]
                for column in [*DAILY_AVERAGE_POLLUTANTS, "O3"]
            },
        }

        if all(value is not None for value in concentrations.values()):
            capped_concentrations = {
                column: min(float(value), MAX_MEP_CONCENTRATIONS[column])
                for column, value in concentrations.items()
            }
            aqi_inputs = [
                (aqi_pollutant, f"{capped_concentrations[column]:.12g}")
                for _, (column, _, aqi_pollutant) in POLLUTANT_INPUTS.items()
            ]
            aqi_value = int(
                aqi_library.to_aqi(aqi_inputs, algo=aqi_library.ALGO_MEP)
            )
            subindices = {
                pollutant: int(
                    aqi_library.to_iaqi(
                        aqi_pollutant,
                        f"{capped_concentrations[column]:.12g}",
                        algo=aqi_library.ALGO_MEP,
                    )
                )
                for pollutant, (column, _, aqi_pollutant) in POLLUTANT_INPUTS.items()
            }
            maximum_subindex = max(subindices.values())
            primary_pollutant = ", ".join(
                pollutant
                for pollutant, subindex in subindices.items()
                if subindex == maximum_subindex
            )
            row.update(
                {
                    "aqi": aqi_value,
                    "primary_pollutant": primary_pollutant,
                    "aqi_category": _aqi_category(aqi_value),
                    **{
                        f"iaqi_{iaqi_column}": value
                        for column, value in subindices.items()
                        for iaqi_column in [POLLUTANT_INPUTS[column][1]]
                    },
                }
            )
        else:
            row.update(
                {
                    f"iaqi_{iaqi_column}": None
                    for _, iaqi_column, _ in POLLUTANT_INPUTS.values()
                }
            )

        daily_rows.append(row)

    return pd.DataFrame(daily_rows)