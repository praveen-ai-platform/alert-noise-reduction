# Alert Noise Reduction POC

A small FastAPI service that reduces alert fatigue before an event reaches an
on-call responder. It accepts a batch of alerts and returns both the actionable
alerts and every suppression decision.

## How It Works

1. Alerts below `minimum_severity` are suppressed.
2. The remaining alerts are grouped by service, alert name, and severity.
3. For each group, the first alert is retained and repeats inside the cooldown
   window are suppressed.
4. A summary reports the received, actionable, suppressed, and reduction counts.

The signature deliberately excludes volatile message text so that changing IDs
or counters in an alert message do not prevent duplicate detection.

## Run Locally

```bash
python -m venv .venv
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` to use the interactive API documentation.

## Example Request

```bash
curl -X POST "http://127.0.0.1:8000/reduce-alert-noise" \
  -H "Content-Type: application/json" \
  --data @data/sample_alerts.json
```

With the supplied sample, the first and post-cooldown warning alerts are kept.
The repeated warning is suppressed as `duplicate_within_cooldown`, and the
informational event is suppressed as `below_minimum_severity`.

## API

- `GET /health` returns a lightweight service health response.
- `POST /reduce-alert-noise` accepts `alerts`, `cooldown_minutes`, and
  `minimum_severity` (`info`, `warning`, or `critical`).

## Test

```bash
python -m unittest discover -s tests -v
```
