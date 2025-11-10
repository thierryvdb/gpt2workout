# csv2fit.py — Convert CSV to FIT (Garmin) and ZWO (Zwift)

This package contains:
- `csv2fit.py`: a simple CSV-to-`.fit.csv` converter compatible with the Garmin FIT SDK.
- `workout_template.csv`: example workout.

## How to Use

1) Prepare your `workout.csv` with the columns:

```
step_type,duration_type,duration_value,target_type,target_value,intensity,notes
```
Optionally include `workout_name` (or use `--name`).

2) Generate the `.fit.csv` (no binary yet):

```bash
python csv2fit.py --in workout.csv --out my_workout --sport cycling
```

3) Optional: also generate `.zwo` (Zwift/MyWhoosh):

```bash
python csv2fit.py --in workout.csv --out my_workout --sport cycling --zwo --ftp 250
```

4) Optional: generate the `.fit` binary automatically if you have the Garmin FIT SDK:

- Download the SDK: https://developer.garmin.com/fit/download/
- Locate `FitCSVTool.jar` from the downloaded package.
- Run:

```bash
python csv2fit.py --in workout.csv --out my_workout --sport cycling --fitcsvtool "/path/to/FitCSVTool.jar"
```

If you prefer to convert manually:
```bash
java -jar FitCSVTool.jar -c my_workout.fit.csv my_workout.fit
```

## Notes

- `target_value` accepts formats such as:
  - `200` or `200-250` (absolute)
  - `85%` or `85%-95%` (percent of FTP for power)
  - `Z2` or `Z2-Z3` (pre-mapped zones; adjust in the script if needed)
- `duration_type`: `time` (seconds), `distance` (meters) or `open` (no explicit end).
- `target_type`: `none`, `power`, `hr`, `cadence`.
- `intensity`: `active` or `rest`.

Tip: If you train by heart rate outdoors, use `hr` with BPM or zone (`Z2`, etc.). For ERG workouts by %FTP on the trainer, use `power` with `%`.

## FIT SDK (Garmin) / JAR

- This repository does not include `FitCSVTool.jar` from the Garmin FIT SDK and you should not version it (SDK license). The path `java/FitCSVTool.jar` is already in `.gitignore`.
- To enable `.fit` binary conversion:
  1. Download the SDK: https://developer.garmin.com/fit/download/
  2. Extract and locate `FitCSVTool.jar` from the package.
  3. Place it at `java/FitCSVTool.jar` in this project or pass the path via `--fitcsvtool`.
- Usage examples for the parameter:
  - Windows: `python csv2fit.py --in workout.csv --out my_workout --sport cycling --fitcsvtool "C:\\path\\to\\FitCSVTool.jar"`
  - macOS/Linux: `python csv2fit.py --in workout.csv --out my_workout --sport cycling --fitcsvtool "/path/to/FitCSVTool.jar"`
- Without the JAR, the script only generates `.fit.csv` (and `.zwo` if `--zwo`).

## CLI Options

- `--in`: input CSV path (required)
- `--out`: output prefix (required)
- `--name`: workout name; if absent, uses the `workout_name` column
- `--sport`: sport (e.g., `cycling`, `running`, `swim`, `strength`)
- `--zwo`: also generate `.zwo` for Zwift/MyWhoosh
- `--ftp`: FTP in watts; required to convert absolute power → fraction in `.zwo`
- `--fitcsvtool`: path to `FitCSVTool.jar` to generate `.fit` automatically

### Examples

```bash
# Generate .fit.csv and .zwo (Zwift), converting absolute watts using FTP=250
python csv2fit.py --in workout.csv --out my_workout --sport cycling --zwo --ftp 250

# Generate .fit automatically using FitCSVTool.jar
python csv2fit.py --in workout.csv --out my_workout --sport cycling --fitcsvtool "/path/to/FitCSVTool.jar"
```

### ZWO Notes

- Power: Zwift expects power as a fraction of FTP. If your CSV uses absolute watts, provide `--ftp`.
- Heart rate (hr): exported as on-screen guidance text (does not control ERG).
- Cadence: a single value in `cadence` defines the cadence target.
- `warmup`/`cooldown`: exported as specific blocks when applicable.

## Workout Prompt (CSV-only)

You are my cycling coach. Create a structured workout for me in **CSV format** only — no explanations.
The CSV must use this exact column order and headers:

```
workout_name,step_type,duration_type,duration_value,target_type,target_value,intensity,notes
```

Rules:
- `duration_type` must be "time" (seconds) or "distance" (meters)
- `target_type` may be: power, hr, cadence, or none
- `power` can be expressed in %FTP (e.g., 85%-95%) or watts
- `hr` can be expressed in bpm or zones (Z2, Z3, etc.)
- `step_type` may include: warmup, interval, recovery, cooldown
- `intensity` can be active or rest
- Do not include comments, markdown, code blocks, or explanations — return only CSV data.
- `workout_name` must be the same for all rows.

Now create a training session with these goals:
- Duration: 1 hour
- Primary objective: Improve FTP
- Include warm-up, 3–4 high-intensity intervals, recoveries, and cooldown
- Make effort progression logical and realistic

Example output (csv):

```
FTP Builder,warmup,time,600,power,55%-65%,active,Warm up
FTP Builder,interval,time,480,power,95%-105%,active,Main interval 1
FTP Builder,recovery,time,180,hr,Z1-Z2,rest,Recover
FTP Builder,interval,time,480,power,95%-105%,active,Main interval 2
FTP Builder,recovery,time,180,hr,Z1-Z2,rest,Recover
FTP Builder,interval,time,480,power,95%-105%,active,Main interval 3
FTP Builder,cooldown,time,600,none,,active,Cool down
```
