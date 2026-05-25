# EV Router

A road trip planner for electric vehicles. Enter an origin and destination, set your starting battery level, and the app recommends the optimal charging stops along the way — with real-time availability, charger speeds, and nearby food and coffee loaded automatically for each stop.

Accessible at [ev.caesartiberius.com](https://ev.caesartiberius.com) (Cloudflare Access — Google login required).

---

## Features

- **Trip Plan** — recommends the minimum number of charging stops using a late-window strategy (stop as far as possible each time to minimize total stops), preferring the fastest charger available in each segment
- **Live availability** — real-time port status from Google Places (green = available, yellow = busy, red = offline, gray = no live data)
- **Charge time estimates** — calculated from kWh needed ÷ effective charge rate with a 1.25× taper factor
- **Inline POI** — nearby restaurants and coffee shops load automatically for each recommended stop
- **All Stations tab** — full list of every charging station found along the route
- **Connector filter** — filter to CCS, NACS, CHAdeMO, J1772, or all
- **Vehicle profile** — configure highway range estimate and minimum arrival charge %
- **PWA** — installable on Android via "Add to Home Screen" in Chrome; works offline (last route cached)
- **Dark map** — custom dark theme with Google Maps

---

## Stack

- **Backend:** Python / Flask / gunicorn
- **APIs:** Google Maps JavaScript API, Google Places API (New), Google Directions API, Google Geocoding API
- **Frontend:** Vanilla JS, Tailwind CSS (CDN), Google Maps JS SDK
- **Hosting:** PinkiPi (Raspberry Pi 5, 8 GB) — systemd service on port 5002
- **Tunnel:** Cloudflare Zero Trust tunnel → `ev.caesartiberius.com`

---

## How the planner works

1. Calls the Google Directions API to get the route polyline and total distance
2. Searches for EV stations along the route using Google Places `searchText` with `routeParameters` (falls back to polyline sampling + `searchNearby` if unsupported)
3. Projects each station onto the polyline to get its mile marker from the origin
4. Runs the planning algorithm:
   - Starting from the origin with the user's battery %, calculates how far the vehicle can travel
   - Identifies the latest reachable window (last 35% of range) and picks the fastest-charging station there
   - Calculates how much charge is needed to reach the next stop or destination, targeting 80% departure (sweet spot before taper)
   - Repeats until the destination is reachable on the remaining charge
5. Returns the trip plan alongside the full station list

---

## Vehicle defaults (BMW i4 M50)

| Parameter | Value |
|---|---|
| Connector | CCS |
| Max charge rate | 200 kW |
| Battery capacity | 83.9 kWh usable |
| Highway range estimate | 240 mi (EPA 270 mi; 240 mi is conservative for highway) |
| Default arrival buffer | 20% |

All vehicle settings are configurable in the app's profile modal.

---

## Project structure

```
app.py                  Flask app — routes and planning logic
config.py               Environment variable loading
lookups.py              Connector label map, network access metadata
wsgi.py                 Gunicorn entry point
templates/index.html    Single-page PWA frontend
static/
  manifest.json         PWA manifest
  sw.js                 Service worker (offline cache)
  icons/                App icons
ev-router.service       systemd unit file
deploy.sh               First-time deploy script (clone, venv, install, enable service)
requirements.txt        Python dependencies
```

---

## Environment variables

Stored in `/home/pi/ev-router/.env` on PinkiPi (not in the repo).

| Variable | Purpose |
|---|---|
| `GOOGLE_MAPS_JS_KEY` | Browser key — restricted to `ev.caesartiberius.com` |
| `GOOGLE_MAPS_SERVER_KEY` | Server key — restricted to PinkiPi's public IP |
| `SECRET_KEY` | Flask session secret |

---

## GCP APIs required

- Maps JavaScript API
- Places API (New)
- Places API *(legacy — required for `libraries=places` in the Maps JS SDK)*
- Directions API
- Geocoding API

---

## Deploying changes

All development happens on Vader (`~/repos/ev-router`). Push to GitHub, then run the deploy script from Vader:

```bash
~/repos/home-automation/scripts/deploy-pinkipi.sh
```

This pulls the repo on PinkiPi and restarts `ev-router.service` along with all other PinkiPi services.
