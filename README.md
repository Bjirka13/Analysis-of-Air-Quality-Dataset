# Analysis of Air Quality Dataset

Proyek ini mengolah data kualitas udara per jam dari 12 stasiun pengukuran di Beijing pada periode 1 Maret 2013 sampai 28 Februari 2017. Pipeline ETL menggabungkan file sumber, memvalidasi data, mempertahankan nilai sensor yang hilang secara parsial, lalu memuat hasilnya ke DuckDB.

## Struktur Proyek

Analysis-of-Air-Quality-Dataset/
├── .env                         # lokal, diabaikan Git
├── .env.example                 # contoh variable path
├── .gitignore
├── README.md
├── Log_Progress.md
├── pyproject.toml
├── requirements.txt
├── air_quality_etl.py           # entrypoint CLI
├── configs/
│   └── pipeline.yaml
├── Data/
│   ├── raw/                      # CSV sumber
│   └── processed/                # warehouse DuckDB
├── src/
│   └── air_quality/
│       ├── __init__.py
│       ├── aqi.py
│       ├── constants.py
│       ├── extract.py
│       ├── imputation.py
│       ├── load.py
│       ├── pipeline.py
│       ├── quality.py
│       └── transform.py
├── sql/
│   ├── schema.sql
│   └── analytics/
├── dashboards/
│   ├── dashboard.py
│   └── cleaned_air_quality_Dataset.csv
├── tests/
│   ├── __init__.py
│   ├── integration/
│   │   └── README.md
│   └── unit/
│       ├── __init__.py
│       └── test_air_quality_etl.py
├── notebooks/                    # eksplorasi dan analisis
└── logs/                         # output lokal, diabaikan Git

## Menjalankan Pipeline

Gunakan Python lokal yang sudah terpasang. Install dependency proyek, termasuk DuckDB:

```powershell
python -m pip install -r requirements.txt
```

Untuk memasang package dalam mode editable:

```powershell
python -m pip install -e .
```

Jalankan ETL dari root proyek:

```powershell
python air_quality_etl.py
```

Secara default, pipeline membaca path dari `configs/pipeline.yaml`. Variabel `AIR_QUALITY_RAW_DIR` dan `AIR_QUALITY_WAREHOUSE` di `.env` dapat meng-override path tersebut; argumen CLI `--raw-dir` dan `--warehouse` memiliki prioritas tertinggi. File sumber tidak diubah. Fact table dibangun ulang dari snapshot sumber setiap kali pipeline dijalankan, sedangkan `etl_run_history` mencatat setiap eksekusi.

## Aturan Data

- Kunci record adalah kombinasi `station` dan `observed_at`; duplikasi kunci menyebabkan pipeline gagal.
- Record dibuang hanya jika seluruh kolom polutan dan cuaca kosong. Missing pada sebagian kolom dipertahankan sebagai `NULL`.
- Nilai polutan negatif dan arah angin di luar 16 kode kompas ditolak.
- Arah angin tetap kategorikal, tidak diubah menjadi angka.

## Tabel DuckDB

- `fact_air_quality`: pengukuran per stasiun dan waktu, termasuk nama file sumber dan nomor record sumber.
- `dim_station`: daftar stasiun.
- `data_quality_summary`: jumlah baris, missing value per kolom, dan kelengkapan jam per stasiun.
- `etl_run_history`: waktu proses, jumlah input/output, serta jumlah record all-empty yang dibuang.
- `daily_air_quality_aqi`: AQI harian MEP, pollutant utama, sub-index, konsentrasi harian, dan jumlah jam valid.

Nilai CO di sumber disimpan dalam µg/m³ dan dikonversi menjadi mg/m³ untuk perhitungan MEP. Konsentrasi di atas breakpoint maksimum library dibatasi ke AQI 500, tanpa mengubah konsentrasi harian yang disimpan. AQI bernilai `NULL` jika data harian tidak memenuhi jumlah jam minimum.

Tes dapat dijalankan dengan:

```powershell
python -m unittest discover -s tests -v
```

Catatan: dashboard belum terintegrasi dengan DuckDB dan belum menampilkan hasil AQI dari `daily_air_quality_aqi`.
