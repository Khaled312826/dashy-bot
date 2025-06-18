# Advanced DoorDash Automation Bot

## Features
- Automated DoorDash account signup (Faker for name/email, SMSPool for OTP)
- Automated DoorDash group order placement
- Custom hosted tracking mini-app with live driver & customer map

## Setup

### Tracking API Server

To power live driver updates, start the tracking API service:

```bash
pip install fastapi uvicorn
uvicorn tracking_api:app --reload --host 0.0.0.0 --port 8001
```

Then serve your static files (including `tracking.html` and `car.png`) on port 8000:

```bash
python -m http.server 8000
```

Navigate to:

```
http://localhost:8000/tracking.html?order_id=<ORDER_ID>
```


1. Unzip and `cd doordash_advanced`
2. `pip install -r requirements.txt`
3. `playwright install`
4. Fill in `.env`
5. Run the webapp server:
   ```
   uvicorn webapp_server:app --host 0.0.0.0 --port 8000
   ```
6. Run the Telegram bot:
   ```
   python bot.py
   ```

## Web App
- Served from `/webapp/tracking.html`
- Polls `/api/track/{order_id}` for live coordinates
- Displays on Leaflet map inside Telegram mini-app
