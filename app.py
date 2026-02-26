from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None

APP_DIR = Path(__file__).parent
SCRIPTS_DIR = APP_DIR / "saved_scripts"
META_FILE = SCRIPTS_DIR / "scripts_meta.json"

IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")



def ensure_storage() -> None:
    SCRIPTS_DIR.mkdir(exist_ok=True)
    if not META_FILE.exists():
        META_FILE.write_text("{}", encoding="utf-8")



def load_metadata() -> dict[str, Any]:
    ensure_storage()
    try:
        return json.loads(META_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}



def save_metadata(meta: dict[str, Any]) -> None:
    META_FILE.write_text(json.dumps(meta, indent=2), encoding="utf-8")



def get_database_url() -> str:
    secret_value = ""
    if "SUPABASE_DB_URL" in st.secrets:
        secret_value = st.secrets["SUPABASE_DB_URL"]

    env_value = os.getenv("SUPABASE_DB_URL", "")
    return secret_value or env_value



def save_uploaded_script(file_name: str, content: bytes) -> Path:
    safe_name = Path(file_name).name
    if not safe_name.endswith(".py"):
        safe_name = f"{safe_name}.py"

    destination = SCRIPTS_DIR / safe_name
    destination.write_bytes(content)

    meta = load_metadata()
    meta[safe_name] = {
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "path": str(destination),
    }
    save_metadata(meta)
    return destination



def script_options() -> list[str]:
    ensure_storage()
    return sorted([path.name for path in SCRIPTS_DIR.glob("*.py")])



def stream_command(command: list[str]) -> int:
    log_container = st.empty()
    lines: list[str] = []

    process = subprocess.Popen(
        command,
        cwd=APP_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    assert process.stdout is not None
    for raw_line in process.stdout:
        line = raw_line.rstrip("\n")
        lines.append(line)
        log_container.code("\n".join(lines[-500:]), language="bash")

    return_code = process.wait()
    return return_code



def validate_view_name(name: str) -> str | None:
    candidate = name.strip()
    if not candidate:
        return None

    if "." in candidate:
        schema, view = candidate.split(".", maxsplit=1)
        if IDENTIFIER_PATTERN.match(schema) and IDENTIFIER_PATTERN.match(view):
            return f'"{schema}"."{view}"'
        return None

    if IDENTIFIER_PATTERN.match(candidate):
        return f'"{candidate}"'

    return None



def refresh_views(db_url: str, view_names: list[str], concurrently: bool) -> tuple[list[str], list[str]]:
    if psycopg is None:
        raise RuntimeError("psycopg is not installed. Run pip install -r requirements.txt")

    successes: list[str] = []
    failures: list[str] = []
    mode = "CONCURRENTLY " if concurrently else ""

    with psycopg.connect(db_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            for raw_name in view_names:
                safe_view = validate_view_name(raw_name)
                if not safe_view:
                    failures.append(f"Invalid view name: {raw_name}")
                    continue

                try:
                    query = f"REFRESH MATERIALIZED VIEW {mode}{safe_view};"
                    cur.execute(query)
                    successes.append(raw_name)
                except Exception as exc:  # noqa: BLE001
                    failures.append(f"{raw_name}: {exc}")

    return successes, failures



def main() -> None:
    st.set_page_config(page_title="Zedalytics Maintenance Console", layout="wide")
    st.title("🛠️ Zedalytics Supabase Maintenance Console")
    st.caption("Upload Python maintenance scripts, rerun them, and refresh materialized views.")

    ensure_storage()

    with st.sidebar:
        st.header("Configuration")
        db_url_input = st.text_input(
            "Supabase DB URL",
            value=get_database_url(),
            type="password",
            help="Stored only for this session unless configured in .streamlit/secrets.toml",
        )
        if db_url_input:
            os.environ["SUPABASE_DB_URL"] = db_url_input

    tab_scripts, tab_views = st.tabs(["Saved Scripts", "Materialized Views"])

    with tab_scripts:
        st.subheader("Upload new script")
        uploaded = st.file_uploader("Upload .py file", type=["py"])
        if uploaded is not None:
            saved_path = save_uploaded_script(uploaded.name, uploaded.getvalue())
            st.success(f"Saved script: {saved_path.name}")

        st.subheader("Run saved script")
        available_scripts = script_options()

        if not available_scripts:
            st.info("No scripts uploaded yet.")
        else:
            selected_script = st.selectbox("Select script", options=available_scripts)
            run_button = st.button("Run Script", type="primary")
            if run_button:
                st.write(f"Running `{selected_script}`...")
                code = stream_command([sys.executable, str(SCRIPTS_DIR / selected_script)])
                if code == 0:
                    st.success(f"`{selected_script}` finished successfully.")
                else:
                    st.error(f"`{selected_script}` exited with code {code}.")

    with tab_views:
        st.subheader("Refresh materialized views")
        views_text = st.text_area(
            "View names (one per line, optionally schema.view)",
            placeholder="analytics.user_activity_mv\npublic.daily_stats_mv",
            height=180,
        )
        concurrently = st.checkbox("Use CONCURRENTLY", value=True)

        if st.button("Refresh Views", type="primary"):
            db_url = get_database_url()
            if not db_url:
                st.error("Set SUPABASE_DB_URL in sidebar, environment, or streamlit secrets.")
            else:
                parsed_views = [line.strip() for line in views_text.splitlines() if line.strip()]
                if not parsed_views:
                    st.warning("Add at least one materialized view name.")
                else:
                    with st.spinner("Refreshing views..."):
                        ok, failed = refresh_views(db_url, parsed_views, concurrently)

                    if ok:
                        st.success(f"Refreshed: {', '.join(ok)}")
                    if failed:
                        st.error("\n".join(failed))


if __name__ == "__main__":
    main()
