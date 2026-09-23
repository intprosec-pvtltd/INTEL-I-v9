# INTEL-I: upload playback, detection preview and alert fixes

This archive contains the integrated project, based on the supplied intel-i-v8-main.zip.

## Confirmed code defects fixed

1. Distributed CameraPipeline decoded uploaded files as fast as possible. It now waits for source presentation-timestamp intervals, falling back to decoder FPS (25 FPS only when metadata is unusable). The legacy upload loop used OUTPUT_STREAM_FPS rather than media timing; it now uses the same clock before inference, including frames later dropped by the scheduler.
2. File EOF was treated like a camera failure and reopened the file. It now retains the last preview until Stop, without replaying. Stop interrupts playback waits.
3. The distributed capture worker published raw frames and discarded processed frames. The central service also discarded its annotated result. The service now returns an encoded annotated image and the camera worker publishes that exact image. Coordinates are never copied onto a different, newer, or differently sized capture frame. Enhancement output is normalized back to the analytics dimensions before detection/tracking.
4. CameraPipeline passed priority to AnalyticsRuntime.process_frame, whose signature did not accept it. The local distributed path could raise TypeError on every inference. The signature now accepts the scheduling metadata.
5. Alert validation could crash when truth-testing a NumPy bounding box, reject track ID zero, or accept non-finite confidence. It now validates those fields explicitly.
6. Cooldown was consumed before final alert validation. Rejected candidates no longer consume it. Restricted-camera severity escalation is no longer overwritten by a later validation call.
7. The Redis realtime subscriber exited permanently after a connection failure. It now reconnects until stopped.
8. The frontend intentionally never recovered persisted alerts. It now polls /alerts/recover every five seconds and on WebSocket connection, limited to records created since this panel mounted. Existing authorization/source filters remain in place. Stable alert IDs prevent duplicate WebSocket/recovery cards; WebSocket evidence updates update the existing card. Upload metadata changes no longer clear current-session alerts.

## Updated files

- backend/alertDecision.py
- backend/db/crud.py
- backend/inference/client.py
- backend/main.py
- backend/runtime/analytics_runtime.py
- backend/services/cameraPipeline.py
- backend/services/realtimeBus.py
- backend/workers/camera_worker.py
- backend/workers/inference_worker.py
- frontend/src/components/Alert.jsx

## New files

- backend/services/playbackClock.py
- backend/tests/test_upload_alert_preview_regression.py
- FIXES_AND_RESTART.md

## Apply on your Windows installation

1. Stop active video analyses in the UI. Stop the API, camera worker, inference worker, and frontend terminals with Ctrl+C.
2. Back up the existing project. Extract this ZIP to a separate directory and copy ONLY the ten updated files and two new backend files listed above into matching paths in your running project. This preserves your local .env, models, venv, vendor, database, uploads, and evidence.
3. No database migration or new project dependency is required for these changes. Keep your existing Redis/Postgres and auxiliary services running.
4. Restart the configured services from the SAME updated backend directory, using your existing environment and ports. In distributed central-inference mode, start inference first, then camera worker, then API. Each requires a separate activated terminal:

```powershell
cd C:\Users\msnum\OneDrive\Desktop\intel-i-v8-main\backend
.\venv\Scripts\Activate.ps1
python -m workers.inference_worker
```

```powershell
cd C:\Users\msnum\OneDrive\Desktop\intel-i-v8-main\backend
.\venv\Scripts\Activate.ps1
python -m workers.camera_worker
```

```powershell
cd C:\Users\msnum\OneDrive\Desktop\intel-i-v8-main\backend
.\venv\Scripts\Activate.ps1
python -m uvicorn main:app --host 0.0.0.0 --port 3000
```

Use your existing OCR/FRS worker commands and configuration. Do not enable another inference mode just to apply this patch. If distributed workers are disabled, restart only the services used in your current mode. Update central inference and camera worker together because annotated-preview responses are a coordinated change.

```powershell
cd C:\Users\msnum\OneDrive\Desktop\intel-i-v8-main\frontend
npm run dev
```

5. Hard-refresh the browser (Ctrl+Shift+R), then start the upload analysis again. Existing in-flight analyses must be restarted.

## Validation and practical limits

The frontend production build passed. The included regression tests cover fixed/variable FPS, missing/backward timestamps, slow-processing timing, interrupted waits, no EOF replay, actual local-runtime call compatibility, NumPy alert boxes, invalid confidence, Redis reconnect, and annotated-image transport. Existing media-timeline, central-inference and distributed-runtime contract tests were also run. Result: 25 tests passed; Python compilation passed; frontend Vite production build passed (existing large-bundle warning only).

```powershell
cd C:\Users\msnum\OneDrive\Desktop\intel-i-v8-main\backend
python -m pytest -q tests/test_upload_alert_preview_regression.py tests/test_media_timeline.py tests/test_central_inference_architecture.py tests/test_distributed_runtime_contract.py
```

Live GPU/model accuracy, PostgreSQL persistence, Telegram delivery, and your Windows deployment were not exercised in this environment. The screenshot alone cannot establish why every displayed box was displaced; the supplied distributed code was discarding annotations altogether. Restart all relevant services to ensure the displayed output comes from this version.

Uploads are paced at 1x source time. Distributed analytics uses the newest available frame and may skip intervening frames when inference is slow. The annotated preview therefore updates at completed inference speed, which is not guaranteed to equal source FPS. The legacy combined processing mode may play slower than real time on overloaded hardware. Neither path intentionally accelerates playback to catch up. If AI stalls for three seconds, distributed preview falls back to raw frames instead of holding a frozen annotated frame indefinitely. JPEG responses add internal network traffic.

A person/car detection is not itself a security alert. Existing behavioral rules, zone restrictions, confidence thresholds, and confirmed watchlist criteria still apply. To validate alerts, use a clip with a known rule violation or confirmed watchlist match; verify the alert in both the current panel and Alert History. Test recovery by briefly interrupting Redis while a qualifying alert is persisted: database recovery should show the missed current-session alert after connectivity returns. Older history remains in Alert History.
