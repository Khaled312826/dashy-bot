import os
import json
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

COOKIE_FILE = "doordash_cookies.json"
BASE_URL = "https://www.doordash.com/consumer/v2/orders"

class RouteResponse(BaseModel):
    route: list  # list of {lat: float, lng: float}

def get_route_osrm(origin, destination):
    lon1, lat1 = origin[1], origin[0]
    lon2, lat2 = destination[1], destination[0]
    url = (
        f"http://router.project-osrm.org/route/v1/driving/"
        f"{lon1},{lat1};{lon2},{lat2}"
        "?overview=full&geometries=geojson"
    )
    r = requests.get(url)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="OSRM routing failed")
    data = r.json()
    coords = data["routes"][0]["geometry"]["coordinates"]
    # swap [lng,lat] to {lat,lng}
    return [{"lat": lat, "lng": lng} for lng, lat in coords]

@app.get("/api/track/{order_id}", response_model=RouteResponse)
async def track(order_id: str):
    # Load cookies
    cookies = {}
    if os.path.exists(COOKIE_FILE):
        raw = json.load(open(COOKIE_FILE))
        cookies = {c['name']: c['value'] for c in raw}
    # Fetch order JSON
    resp = requests.get(f"{BASE_URL}/{order_id}", cookies=cookies)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Order fetch failed")
    data = resp.json()
    # Extract driver location
    try:
        driver = data['delivery']['driver_location']
        origin = (driver['latitude'], driver['longitude'])
    except Exception:
        raise HTTPException(status_code=404, detail="Driver not assigned yet")
    # Extract dropoff (customer) location
    try:
        dropoff = data['delivery']['dropoff_location']
        dest = (dropoff['latitude'], dropoff['longitude'])
    except Exception:
        raise HTTPException(status_code=404, detail="Dropoff location missing")
    # Compute route via OSRM
    route = get_route_osrm(origin, dest)
    return {"route": route}
