# Running the K305 dashboard

This guide starts the local Streamlit dashboard and builds the data files it
needs from the 29 October 2026 NSE object-list data included with this
repository.

## 1. Open a terminal in the repository

Run all commands below from the project root:

```bash
cd /home/arman/Projects/pedestrian-and-cyclists-at-the-intersection-data-science-project
```

## 2. Install the Python packages

Python 3.10 or newer is required. Installing into a virtual environment is
recommended, but optional.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

## 3. Build the dashboard data

The dashboard does not read the 288 raw JSON files while it is running. Build
its compact data bundle first. In this checkout, the raw NSE object-list files
are stored under a folder whose name contains spaces, so keep the quotation
marks:

```bash
python build_dashboard_data.py \
  --data-dir "database/Data from date of 28.10, 29.10./newsense/object_list/k305_object_list_2026-10-29_aggregation_5min"
```

The first full build takes about five minutes. It writes generated files such
as `dashboard/data/counts_15min_clean.parquet`. These files are deliberately
not committed to Git.

## 4. Start the dashboard

```bash
streamlit run dashboard/Overview.py
```

Streamlit will print a local URL. Open [http://localhost:8501](http://localhost:8501)
if it does not open a browser automatically. Leave the terminal running while
using the dashboard; press `Ctrl+C` there to stop it.

## After code or data changes

Restart the Streamlit server after pulling code changes, especially when files
under `dashboard/lib/` change:

```bash
Ctrl+C
streamlit run dashboard/Overview.py
```

Re-run the build command in step 3 after changing the raw NSE data or the
dashboard data-building code.

## Troubleshooting

### `dashboard/data/counts_15min_clean.parquet is missing`

The generated data bundle is absent or incomplete. Run the command in step 3,
wait for it to finish successfully, then restart Streamlit.

### `streamlit: command not found`

Activate the virtual environment from step 2, or invoke Streamlit through the
same Python installation:

```bash
python -m streamlit run dashboard/Overview.py
```

### A page says that only its data is missing

The core dashboard data is built in step 3. Some optional pages also rely on
other local sources (for example camera videos, traffic-signal logs, or Ouster
LiDAR files). The page reports the specific missing input and the command to
generate its associated data.

For a description of every dashboard page and the optional data sources, see
[the dashboard reference](../dashboard/README.md).
