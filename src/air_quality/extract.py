from pathlib import Path

import pandas as pd

from .constants import RAW_COLUMNS


def extract_raw_data(raw_dir: Path) -> pd.DataFrame:
    files = sorted(raw_dir.glob("PRSA_Data_*_20130301-20170228.csv"))
    if not files:
        raise FileNotFoundError(f"No source CSV files found in {raw_dir}")

    frames: list[pd.DataFrame] = []
    for path in files:
        frame = pd.read_csv(path)
        missing_columns = RAW_COLUMNS.difference(frame.columns)
        if missing_columns:
            raise ValueError(f"{path.name} is missing columns: {sorted(missing_columns)}")

        expected_station = path.name.removeprefix("PRSA_Data_").removesuffix(
            "_20130301-20170228.csv"
        )
        stations = frame["station"].dropna().unique().tolist()
        if stations != [expected_station]:
            raise ValueError(
                f"Station value in {path.name} does not match its filename: {stations}"
            )

        frame["source_file"] = path.name
        frames.append(frame)

    return pd.concat(frames, ignore_index=True)