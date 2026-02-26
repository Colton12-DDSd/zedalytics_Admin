# Zedalytics Supabase Maintenance App

A local Streamlit app for running repeatable maintenance scripts and refreshing Supabase materialized views.

## Features

- Upload Python scripts (`.py`) and save them to a local `saved_scripts/` folder.
- Rerun any saved script with one click.
- Live console output while scripts run.
- Refresh one or more Supabase materialized views directly from the UI.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

Then open the URL Streamlit prints (usually `http://localhost:8501`).

## Supabase DB URL

Set `SUPABASE_DB_URL` in one of these ways:

1. In the app sidebar (session-only), or
2. Environment variable:

```bash
export SUPABASE_DB_URL='postgresql://USER:PASSWORD@HOST:5432/postgres'
```

3. Streamlit secrets file: `.streamlit/secrets.toml`

```toml
SUPABASE_DB_URL = "postgresql://USER:PASSWORD@HOST:5432/postgres"
```

## Notes

- Materialized view names accept either `view_name` or `schema.view_name`.
- View names are validated before SQL execution.
- For `CONCURRENTLY`, each materialized view must have a unique index and cannot be inside a transaction.
