CREATE TABLE IF NOT EXISTS fact_air_quality (
    station VARCHAR NOT NULL,
    observed_at TIMESTAMP NOT NULL,
    source_file VARCHAR,
    source_no BIGINT,
    "PM2.5" DOUBLE,
    "PM10" DOUBLE,
    SO2 DOUBLE,
    NO2 DOUBLE,
    CO DOUBLE,
    O3 DOUBLE,
    TEMP DOUBLE,
    PRES DOUBLE,
    DEWP DOUBLE,
    RAIN DOUBLE,
    wd VARCHAR,
    WSPM DOUBLE,
    PRIMARY KEY (station, observed_at)
);

CREATE TABLE IF NOT EXISTS dim_station (
    station VARCHAR PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS data_quality_summary (
    station VARCHAR PRIMARY KEY,
    row_count BIGINT,
    duplicate_key_count BIGINT,
    rows_with_any_missing_measurement BIGINT,
    missing_hours_inside_range BIGINT,
    min_observed_at TIMESTAMP,
    max_observed_at TIMESTAMP,
    missing_by_column_json VARCHAR
);

CREATE TABLE IF NOT EXISTS etl_run_history (
    run_started_at TIMESTAMPTZ,
    source_file_count INTEGER,
    station_count INTEGER,
    row_count BIGINT,
    min_observed_at TIMESTAMP,
    max_observed_at TIMESTAMP,
    dropped_empty_measurement_rows BIGINT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS daily_air_quality_aqi (
    station VARCHAR NOT NULL,
    observed_date DATE NOT NULL,
    aqi INTEGER,
    primary_pollutant VARCHAR,
    aqi_category VARCHAR,
    pm25_24h DOUBLE,
    pm10_24h DOUBLE,
    so2_24h DOUBLE,
    no2_24h DOUBLE,
    co_24h DOUBLE,
    o3_8h_max DOUBLE,
    valid_hours_pm25 INTEGER,
    valid_hours_pm10 INTEGER,
    valid_hours_so2 INTEGER,
    valid_hours_no2 INTEGER,
    valid_hours_co INTEGER,
    valid_hours_o3 INTEGER,
    iaqi_pm25 INTEGER,
    iaqi_pm10 INTEGER,
    iaqi_so2_24h INTEGER,
    iaqi_no2_24h INTEGER,
    iaqi_co_24h INTEGER,
    iaqi_o3_8h_max INTEGER,
    PRIMARY KEY (station, observed_date)
);