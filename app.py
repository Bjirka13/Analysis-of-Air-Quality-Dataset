import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Dashboard Kinerja Kualitas Udara", layout="wide")

# ==========================================
# 1. KONEKSI DATABASE & INISIALISASI
# ==========================================
@st.cache_resource
def get_db():
    return duckdb.connect('data/processed/air_quality.duckdb', read_only=True)

conn = get_db()

# Ambil batasan tanggal dan daftar pilihan untuk filter
bounds = conn.execute("SELECT MIN(observed_at::DATE), MAX(observed_at::DATE) FROM fact_air_quality").fetchone()
min_date, max_date = bounds
stations_list = conn.execute("SELECT station FROM dim_station ORDER BY station").df()['station'].tolist()
years_list = conn.execute("SELECT DISTINCT EXTRACT(YEAR FROM observed_at) as y FROM fact_air_quality ORDER BY y").df()['y'].tolist()

# ==========================================
# 2. PANEL FILTER (ATAS)
# ==========================================
st.title("Dashboard Kinerja Kualitas Udara")

col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    date_range = st.date_input("Rentang Tanggal", [min_date, max_date], min_value=min_date, max_value=max_date)
with col_f2:
    selected_stations = st.multiselect("Filter Stasiun", stations_list, default=[])
with col_f3:
    selected_years = st.multiselect("Filter Tahun", years_list, default=[])

# ==========================================
# 3. PEMBENTUKAN KONDISI QUERY (DYNAMIC WHERE)
# ==========================================
where_clauses = []
if len(date_range) == 2:
    where_clauses.append(f"observed_at::DATE BETWEEN '{date_range[0]}' AND '{date_range[1]}'")
if selected_stations:
    stations_str = ",".join([f"'{s}'" for s in selected_stations])
    where_clauses.append(f"station IN ({stations_str})")
if selected_years:
    years_str = ",".join(map(str, selected_years))
    where_clauses.append(f"EXTRACT(YEAR FROM observed_at) IN ({years_str})")

where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
where_sql = f"WHERE {where_sql}"

# ==========================================
# 4. EKSEKUSI DATA METRIK & KPI
# ==========================================
df_ranking = conn.execute(f"""
    SELECT 
        station, 
        AVG("PM2.5") as avg_pm25, 
        AVG(CASE WHEN "PM2.5" > 75 THEN 1.0 ELSE 0.0 END) * 100 as pct_hours_above
    FROM fact_air_quality 
    {where_sql} 
    GROUP BY station 
    ORDER BY avg_pm25 DESC
""").df()

if df_ranking.empty:
    st.warning("Data kosong untuk filter yang dipilih.")
    st.stop()

# Kalkulasi KPI
worst_station = df_ranking.iloc[0]['station']
worst_pm = df_ranking.iloc[0]['avg_pm25']
best_station = df_ranking.iloc[-1]['station']
best_pm = df_ranking.iloc[-1]['avg_pm25']
avg_pct_hours = df_ranking['pct_hours_above'].mean()

# Agregasi Waktu
df_time = conn.execute(f"""
    SELECT 
        EXTRACT(MONTH FROM observed_at) as month,
        EXTRACT(HOUR FROM observed_at) as hour,
        AVG("PM2.5") as avg_pm25
    FROM fact_air_quality 
    {where_sql} 
    GROUP BY month, hour
""").df()

worst_month = df_time.groupby('month')['avg_pm25'].mean().idxmax()
peak_hour = df_time.groupby('hour')['avg_pm25'].mean().idxmax()

# ==========================================
# 5. RENDER KPI BARIS ATAS
# ==========================================
st.markdown("---")
kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
kpi1.metric("🚨 Stasiun Terburuk", f"{worst_station}", f"{worst_pm:.1f} µg/m³", delta_color="inverse")
kpi2.metric("🏆 Stasiun Terbaik", f"{best_station}", f"{best_pm:.1f} µg/m³", delta_color="normal")
kpi3.metric("⚠️ Jam > Ambang MEP (75)", f"{avg_pct_hours:.1f} %")
kpi4.metric("📅 Bulan Terburuk", f"Bulan ke-{int(worst_month)}")
kpi5.metric("⏰ Jam Puncak Polusi", f"{int(peak_hour)}:00")
st.markdown("---")

# ==========================================
# 6. ROW 1: BAR RANKING & HEATMAP POLUTAN
# ==========================================
r1c1, r1c2 = st.columns(2)

with r1c1:
    # Bar ranking stasiun
    fig_rank = px.bar(df_ranking, x='avg_pm25', y='station', orientation='h', 
                      title=" Peringkat Stasiun (PM2.5)", color='avg_pm25', color_continuous_scale="Reds")
    fig_rank.update_layout(yaxis={'categoryorder':'total ascending'}, height=400)
    st.plotly_chart(fig_rank, use_container_width=True)

with r1c2:
    #  Heatmap polutan di 5 stasiun terburuk (Rasio batas aman MEP China)
    # Standar Harian (Grade II MEP GB 3095-2012): PM2.5=75, PM10=150, SO2=150, NO2=80, CO=4000, O3=160
    top5_stations = ",".join([f"'{s}'" for s in df_ranking['station'].head(5)])
    where_heatmap = f"{where_sql} AND station IN ({top5_stations})"
    
    df_heat = conn.execute(f"""
        SELECT 
            station,
            AVG("PM2.5")/75 as "PM2.5", 
            AVG("PM10")/150 as "PM10", 
            AVG(SO2)/150 as SO2, 
            AVG(NO2)/80 as NO2, 
            AVG(CO)/4000 as CO, 
            AVG(O3)/160 as O3
        FROM fact_air_quality 
        {where_heatmap} 
        GROUP BY station
    """).df().set_index('station')
    
    fig_heat = px.imshow(df_heat, text_auto=".1f", aspect="auto", 
                         title=" Rasio Polutan - Standar China (MEP Grade II)", color_continuous_scale="Reds")
    fig_heat.update_layout(height=400)
    st.plotly_chart(fig_heat, use_container_width=True)

# ==========================================
# 7. ROW 2: TREN WAKTU (BULAN & JAM)
# ==========================================
r2c1, r2c2 = st.columns(2)

with r2c1:
    #  Line PM2.5 per bulan
    df_month = df_time.groupby('month')['avg_pm25'].mean().reset_index()
    fig_month = px.line(df_month, x='month', y='avg_pm25', markers=True, 
                        title=" Rata-Rata PM2.5 per Bulan")
    fig_month.update_xaxes(dtick=1)
    st.plotly_chart(fig_month, use_container_width=True)

with r2c2:
    #  Line PM2.5 per jam
    df_hour = df_time.groupby('hour')['avg_pm25'].mean().reset_index()
    fig_hour = px.line(df_hour, x='hour', y='avg_pm25', markers=True, 
                       title=" Rata-Rata PM2.5 per Jam (Pola Harian)")
    fig_hour.update_xaxes(dtick=2)
    st.plotly_chart(fig_hour, use_container_width=True)

# ==========================================
# 8. ROW 3: PENGARUH METEOROLOGI (WIND)
# ==========================================
r3c1, r3c2 = st.columns(2)

with r3c1:
    #  Wind Rose (Arah Angin)
    df_wind_rose = conn.execute(f"""
        SELECT wd, AVG("PM2.5") as avg_pm25
        FROM fact_air_quality 
        {where_sql} AND wd IS NOT NULL 
        GROUP BY wd
    """).df()
    fig_wind_rose = px.bar_polar(df_wind_rose, r="avg_pm25", theta="wd", 
                                 title=" Wind Rose: PM2.5 per Arah Angin",
                                 color="avg_pm25", color_continuous_scale="Oranges")
    st.plotly_chart(fig_wind_rose, use_container_width=True)

with r3c2:
    #  Bar PM2.5 per Kelas Kecepatan Angin
    df_wspm = conn.execute(f"""
        SELECT 
            CASE 
                WHEN WSPM < 1 THEN '1. Tenang (<1 m/s)'
                WHEN WSPM >= 1 AND WSPM < 3 THEN '2. Lemah (1-3 m/s)'
                WHEN WSPM >= 3 AND WSPM < 5 THEN '3. Sedang (3-5 m/s)'
                ELSE '4. Kuat (>=5 m/s)'
            END as wind_class,
            AVG("PM2.5") as avg_pm25
        FROM fact_air_quality 
        {where_sql} AND WSPM IS NOT NULL 
        GROUP BY wind_class 
        ORDER BY wind_class
    """).df()
    fig_wspm = px.bar(df_wspm, x='wind_class', y='avg_pm25', 
                      title=" PM2.5 per Kelas Kecepatan Angin (WSPM)",
                      color='avg_pm25', color_continuous_scale="Blues")
    st.plotly_chart(fig_wspm, use_container_width=True)