# EGN 321 Module 7 Assignment 7.1

## Unattended temperature monitoring

**Juan Pablo Osorio**

This application extends my Module 6 SQLite history with a Flask dashboard, continuous one-second replay, validation, persistent alert state, timer-based stale detection, transactional event logging, and a process supervisor. Original Module 6 records are preserved. A separate, clearly labeled fixture sequence demonstrates alert activation, clearing, missing data, silence, and crash recovery.

## Start the system

Python 3.10 or later is required. From this folder:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python supervisor.py
```

Open **http://127.0.0.1:5071**. This one entry point starts Flask and its replay worker. The page refreshes every two seconds; data are processed every second. Stop the supervisor with Ctrl+C; it terminates its child. On Windows, activate with `.venv\Scripts\activate` and use the appropriate shell environment-variable syntax. The actual recovery test was run on macOS, not Windows.

The default mode replays the original 125 Module 6 records in order, then starts another replay cycle. Repeated playback is labeled classroom replay; receipt times are not represented as original measurement times. The dashboard includes a separate full view of the preserved Module 6 archive and recent replay history. It requires no external chart service or CDN.

## Source and database

- Input: `data/module6_history.db`, copied from my [Module 6 Assignment 6.1](https://github.com/juanosorio-alt/EGN321-Assignment6-1) primary database.
- Sensor: virtual NTC temperature sensor, degrees Celsius, from the earlier Velxio project.
- Archive: 125 records; 103 OK, 19 OUT_OF_RANGE, 2 SUSPICIOUS and 1 MISSING.
- The original `sensor_readings` and `metadata` tables remain unchanged. Their timestamps were reconstructed in Module 6 for classroom replay starting October 1, 2026 at 12:00:00, with UTC as a convention. They are not actual acquisition times.
- On first startup, SQLite backup creates `runtime/monitor.db` from the supplied Module 6 database. Startup never overwrites an existing runtime database.
- New replay rows go into `live_readings`, with source record ID, source timestamp, UTC receipt timestamp, raw value, accepted value, status, provenance and replay cycle. `state` holds the checkpoint, alert and heartbeat; `events` holds transactional logs.
- The included database is sufficient for reproduction; no Module 6 download is needed. Source hash and links are in `source_manifest.json`.

## Validation and missing data

The expected replay interval is **one second**. Finite Celsius values from 0 through 50 are accepted, subject to source status. Missing or rejected input stores `NULL` as its accepted value; it is never replaced by zero or the last valid reading. Original rejection statuses remain auditable. SUSPICIOUS values retain their numeric value and source status, but do not activate or clear alerts. They degrade current data status and reset pending persistence.

The dashboard shows `Unavailable` when the latest input is invalid, missing, suspicious or more than three seconds old. It separately identifies the latest received timestamp. A 0.2-second timer continues evaluating health even when no source row arrives. Graphs break at unavailable values, receipt gaps greater than 1.8 seconds, and original run boundaries; no interpolation fills missing intervals.

## Threshold and alert control

This classroom monitor flags a sustained warm condition: **three consecutive OK readings at or above 30.0 °C** activate the alert. Three readings reject an isolated spike. The threshold is above the 22–29 °C range of OK values in the preserved history; it is a demonstration operating threshold, not a hardware safety limit.

Once active, the alert clears only on an OK value **at or below 28.5 °C**. This hysteresis prevents toggling near 30 °C. Missing, rejected or suspicious input resets the pending high count but cannot clear an active alert. A stale interval resets pending persistence. Alert state survives a restart, but the pending high count resets so samples on opposite sides of an interruption are not counted as consecutive.

## System health

| State | Meaning |
|---|---|
| RECOVERING | Application has started and no valid input has yet arrived, within the initial grace period. Startup is also logged as recovering. |
| HEALTHY | Recent OK data, no active threshold alert, and a recent worker heartbeat. |
| DEGRADED | Active threshold alert, invalid/missing/suspicious latest input, or more than 3 seconds without valid input. |
| FAILED | More than 8 seconds without valid input, or worker heartbeat older than 8 seconds. |

A fresh valid sample restores the appropriate state; an active temperature alert still means DEGRADED. Invalid arrivals cannot keep the valid-data age fresh. Stale detection uses receipt time during replay, never the old archive date. The health endpoint is `/health`; full state is `/api/status`.

## Startup and restart

`supervisor.py` launches the entire application and waits for its exit. After an unexpected exit it logs the exit code, waits one second, and launches a new process. The application resumes its persisted source cursor; the reading, alert update and cursor advance commit in one transaction. A crash cannot commit a reading without also advancing its checkpoint.

Five consecutive exits in under ten seconds each stop automatic retries and produce `RESTART_LIMIT_REACHED`. The supervisor must remain alive. This is a **process-manager demonstration**, not OS boot installation or a hosted service. No automatic launch after a computer reboot is claimed or installed on the user's machine. Keep the command running on an awake host for unattended operation.

## Logs

- `runtime/monitor.db`, `events` table: normal startup, application restart, every processed reading, invalid/missing conditions, stale/failure transitions, alert activation and clearing, health changes, and worker exceptions.
- `runtime/supervisor.jsonl`: supervisor startup, child process IDs, exit codes, restart scheduling and shutdown.
- `runtime/application_console.log`: Flask HTTP activity and application errors, including server errors.
- Submitted test exports: `evidence/application_events.jsonl`, `evidence/supervisor.jsonl`, and `evidence/application_console.log`.

A hard kill cannot execute code inside the killed process. The supervisor records that interruption, and the new application process records its restart. Events and readings use the same SQLite transaction so their order remains auditable. Logs are local; no email or external notification is sent.

## Reproduce the controlled evidence run

The normal history does not contain three consecutive accepted high values. The controlled test uses explicitly injected temperatures and pauses, not invented historical measurements. It keeps the complete Module 6 archive alongside those fixtures.

```bash
python -m unittest -v
python verify_recovery.py
```

The verification launches a real supervisor and Flask child on port 5071. It saves HTTP dashboard responses and JSON state for each condition, sends **SIGKILL to the actual Flask child**, and waits for a different child PID and a healthy HTTP response. It verifies SQLite integrity and exact preservation of all prior rows and all 125 archive records. It shuts down its own supervisor when finished. Do not run the ordinary supervisor on the same port during this test.

To protect existing evidence, the verifier refuses to reuse `runtime/verification`. For another run, extract a fresh project copy. Both monitoring and automated verification require Flask only. Browser screenshots were captured separately with the Codex in-app browser against the running normal-history application. Unix SIGKILL verification is intended for macOS or Linux.

## Evidence map

| Requirement | Evidence |
|---|---|
| Dashboard, current reading and history | `evidence/dashboard_browser.png`, `evidence/history_browser.png` and `01_dashboard_running.json` |
| Alert active | `evidence/02_alert_active.html` and JSON |
| Alert cleared | `evidence/03_alert_cleared.html` and JSON |
| Missing data | `evidence/04_missing.html` and JSON |
| Stale data and failed health | `evidence/05_stale_failed.html` and JSON |
| Before interruption | `evidence/06_before_interruption.html` and JSON |
| Restart and final healthy state | `evidence/07_recovered_healthy.html`, JSON and `recovery_result.json` |
| Database and logs | `evidence/verified_monitor.db` and three log exports |
| Logic and storage tests | `evidence/unit_tests.txt` |

The two PNG screenshots are actual browser captures of the running Module 6 history mode on localhost port 5072. The numbered HTML files are saved HTTP responses from the controlled demo on port 5071, not screenshots. Their companion JSON records document the observed states; small timing differences can occur between the JSON and HTML requests. Saved HTML is historical evidence, not a live monitor.

## Recovery scope and limitations

Automatic recovery covers a child-process crash and worker exceptions that terminate the application, while the supervisor, host and SQLite storage remain operational. New valid input clears stale/failure health without a restart. Replaying the stored cursor prevents silent loss of committed history.

Human intervention is still required for supervisor/host failure, suspended computers, corrupted databases, exhausted disks, invalid permissions/configuration, port conflicts, repeated crash loops and a source that never returns. A hung process is not automatically killed by this supervisor; heartbeat failure is reported while the dashboard remains responsive. SQLite and logs grow without retention limits in this classroom implementation. Run one supervisor per runtime directory. The Flask development server is bound to localhost and is not presented as a hardened production deployment. No physical sensor, remote deployment or OS reboot recovery was tested.

## References and AI use

The [instructor's Module 7 repository](https://github.com/ivansuarez-AU/EGN321_Module7_Assignment7_1) guided the requirements and persistence/hysteresis approach. This project adds its own HTML dashboard, Module 6 archive integration, receipt-time monitoring, transactional checkpoint and recovery verification. Instructor screenshots and logs are not reused as student execution evidence. Meaningful AI assistance and verification are recorded in `AI_LOG.md`.

GitHub repository: https://github.com/juanosorio-alt/EGN321-Assignment7-1
