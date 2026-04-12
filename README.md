# 🛰️ GNSS Log Analyzer

A GNSS data pipeline built using **Medallion Architecture (Bronze/Silver)** to ingest, validate, and visualize satellite telemetry data in real time.

---

## 🚀 Features

- **Medallion Data Pipeline**
  - Bronze layer: raw GNSS data storage
  - Silver layer: validated & cleaned dataset

- **Time-Series Optimized Database**
  - Built on **TimescaleDB (PostgreSQL)**
  - Efficient handling of high-frequency GNSS logs

- **Data Quality Engine**
  - Satellite count filtering
  - SNR (signal strength) validation
  - Coordinate integrity checks
  - Full rejection logging for traceability

- **Interactive Dashboards (Streamlit)**
  - 📍 Operational Dashboard: Live GNSS path + altitude trends
  - 📊 Engineering Dashboard: Pipeline health + error analytics

- **Reliable Ingestion**
  - Idempotent processing using Streamlit session state
  - Prevents duplicate ingestion on refresh

---

## 🧠 Project Goal

This project simulates a real-world **data engineering pipeline for satellite telemetry systems**, focusing on:

- Data reliability & validation
- Observability (why data is rejected)
- Scalable time-series storage design
- Production-style ETL architecture

---

## 🛠️ Tech Stack

- Python (Pandas, SQLAlchemy)
- Streamlit (Dashboard UI)
- PostgreSQL + TimescaleDB
- Docker & Docker Compose

---

## ▶️ How to Run

### 1. Clone repository
```bash
git clone https://github.com/arinaafrin/GnssLogAnalyzer.git
cd GnssLogAnalyzer
```
### 2. Start system
```bash
docker-compose up --build -d
```
### 3. Open dashboard
http://localhost:8501
