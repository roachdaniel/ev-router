import math
import os
import requests
from flask import Flask, jsonify, request, render_template, send_from_directory, Response

import config
from lookups import CONNECTOR_LABELS, get_network_access

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

DIRECTIONS_URL    = 'https://maps.googleapis.com/maps/api/directions/json'
GEOCODE_URL       = 'https://maps.googleapis.com/maps/api/geocode/json'
PLACES_SEARCH_URL = 'https://places.googleapis.com/v1/places:searchText'
PLACES_NEARBY_URL = 'https://places.googleapis.com/v1/places:searchNearby'


# ── Helpers ──────────────────────────────────────────────────────────────────

def _places_headers(field_mask: str) -> dict:
    return {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': config.GOOGLE_MAPS_SERVER_KEY,
        'X-Goog-FieldMask': field_mask,
    }


def _decode_polyline(encoded: str) -> list[tuple[float, float]]:
    """Decode a Google encoded polyline string into (lat, lng) pairs."""
    coords, index, lat, lng = [], 0, 0, 0
    while index < len(encoded):
        for is_lng in (False, True):
            result, shift = 1, 0
            while True:
                b = ord(encoded[index]) - 63 - 1
                index += 1
                result += b << shift
                shift += 5
                if b < 0x1f:
                    break
            val = lat if not is_lng else lng
            delta = (~result >> 1) if (result & 1) else (result >> 1)
            if not is_lng:
                lat += delta
            else:
                lng += delta
        coords.append((lat / 1e5, lng / 1e5))
    return coords


def _sample_polyline(coords: list, interval_miles: float = 35) -> list:
    """Return evenly spaced sample points along the polyline."""
    if not coords:
        return []
    samples = [coords[0]]
    accumulated = 0.0
    for i in range(1, len(coords)):
        a, b = coords[i - 1], coords[i]
        dlat = math.radians(b[0] - a[0])
        dlng = math.radians(b[1] - a[1])
        h = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(a[0])) * math.cos(math.radians(b[0])) * math.sin(dlng / 2) ** 2)
        seg_miles = 3958.8 * 2 * math.asin(math.sqrt(h))
        accumulated += seg_miles
        if accumulated >= interval_miles:
            samples.append(b)
            accumulated = 0.0
    if coords[-1] not in samples:
        samples.append(coords[-1])
    return samples


def _enrich_station(place: dict) -> dict:
    name = place.get('displayName', {}).get('text', 'Unknown Station')
    location = place.get('location', {})
    ev = place.get('evChargeOptions', {})
    aggregations = ev.get('connectorAggregation', [])

    connectors = []
    total_ports = ev.get('connectorCount', 0)
    available = 0
    out_of_service = 0
    max_kw = 0
    freshest_update = None

    for agg in aggregations:
        ctype = agg.get('type', '')
        label = CONNECTOR_LABELS.get(ctype, ctype.replace('EV_CONNECTOR_TYPE_', ''))
        kw = agg.get('maxChargeRateKw', 0)
        count = agg.get('count', 0)
        avail = agg.get('availableCount')
        oos = agg.get('outOfServiceCount', 0)
        updated = agg.get('availabilityLastUpdateTime')

        if label not in ('Other', '') and count > 0:
            connectors.append({'label': label, 'kw': kw, 'count': count})

        if kw and kw > max_kw:
            max_kw = kw
        if avail is not None:
            available += avail
        out_of_service += oos
        if updated and (freshest_update is None or updated > freshest_update):
            freshest_update = updated

    # Status color
    has_live_data = any(agg.get('availableCount') is not None for agg in aggregations)
    if has_live_data:
        if out_of_service >= total_ports > 0:
            status_color = 'red'
        elif available == 0:
            status_color = 'yellow'
        else:
            status_color = 'green'
    else:
        status_color = 'gray'

    access = get_network_access(name)

    return {
        'place_id':      place.get('id', ''),
        'name':          name,
        'address':       place.get('formattedAddress', ''),
        'lat':           location.get('latitude'),
        'lng':           location.get('longitude'),
        'connectors':    connectors,
        'total_ports':   total_ports,
        'available':     available if has_live_data else None,
        'out_of_service': out_of_service,
        'max_kw':        int(max_kw) if max_kw else None,
        'status_color':  status_color,
        'live_data':     has_live_data,
        'last_updated':  freshest_update,
        **access,
    }


def _get_ev_stations_along_route(encoded_polyline: str) -> list:
    """Search for EV stations along the route using searchText + routeParameters.
    Falls back to sampling + searchNearby if routeParameters is unsupported."""

    ev_field_mask = (
        'places.id,places.displayName,places.formattedAddress,'
        'places.location,places.evChargeOptions,places.businessStatus'
    )

    # Primary: searchText with routeParameters (single API call)
    try:
        resp = requests.post(
            PLACES_SEARCH_URL,
            json={
                'textQuery': 'EV charging station',
                'maxResultCount': 20,
                'routeParameters': {
                    'polyline': {'encodedPolyline': encoded_polyline}
                },
            },
            headers=_places_headers(ev_field_mask),
            timeout=10,
        )
        if resp.status_code == 200:
            places = resp.json().get('places', [])
            seen, stations = set(), []
            for p in places:
                pid = p.get('id')
                if pid and pid not in seen:
                    seen.add(pid)
                    station = _enrich_station(p)
                    if station['lat'] is not None:
                        stations.append(station)
            if stations:
                return stations
    except requests.RequestException:
        pass

    # Fallback: sample polyline and searchNearby at each point
    coords = _decode_polyline(encoded_polyline)
    samples = _sample_polyline(coords, interval_miles=35)

    seen, stations = set(), []
    for lat, lng in samples:
        try:
            resp = requests.post(
                PLACES_NEARBY_URL,
                json={
                    'includedTypes': ['electric_vehicle_charging_station'],
                    'maxResultCount': 10,
                    'locationRestriction': {
                        'circle': {
                            'center': {'latitude': lat, 'longitude': lng},
                            'radius': 40000,
                        }
                    },
                },
                headers=_places_headers(ev_field_mask),
                timeout=8,
            )
            if resp.status_code == 200:
                for p in resp.json().get('places', []):
                    pid = p.get('id')
                    if pid and pid not in seen:
                        seen.add(pid)
                        station = _enrich_station(p)
                        if station['lat'] is not None:
                            stations.append(station)
        except requests.RequestException:
            continue

    return stations


# ── Routes ────────────────────────────────────────────────────────────────────

@app.after_request
def security_headers(resp):
    resp.headers['X-Frame-Options'] = 'DENY'
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    resp.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://maps.googleapis.com https://maps.gstatic.com https://cdn.tailwindcss.com https://static.cloudflareinsights.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.tailwindcss.com; "
        "font-src https://fonts.gstatic.com; "
        "img-src 'self' data: blob: https://*.googleapis.com https://*.gstatic.com; "
        "connect-src 'self' https://maps.googleapis.com https://places.googleapis.com https://*.cloudflareaccess.com https://static.cloudflareinsights.com; "
        "frame-src https://*.cloudflareaccess.com; "
        "worker-src 'self' blob:;"
    )
    return resp


@app.get('/')
def index():
    return render_template('index.html', maps_key=config.GOOGLE_MAPS_JS_KEY)


@app.get('/sw.js')
def service_worker():
    resp = send_from_directory(app.static_folder, 'sw.js')
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Service-Worker-Allowed'] = '/'
    return resp


@app.get('/api/geocode')
def geocode():
    address = request.args.get('address', '').strip()
    if not address:
        return jsonify({'error': 'address required'}), 400
    try:
        r = requests.get(GEOCODE_URL,
                         params={'address': address, 'key': config.GOOGLE_MAPS_SERVER_KEY},
                         timeout=5)
        data = r.json()
    except requests.RequestException:
        return jsonify({'error': 'geocoding timeout'}), 504

    status = data.get('status')
    if status == 'ZERO_RESULTS':
        return jsonify({'error': 'address not found'}), 404
    if status != 'OK':
        return jsonify({'error': f'geocoding error: {status}'}), 502

    loc = data['results'][0]['geometry']['location']
    return jsonify({
        'lat': loc['lat'],
        'lng': loc['lng'],
        'formatted_address': data['results'][0]['formatted_address'],
    })


@app.post('/api/route')
def route():
    data = request.get_json(silent=True) or {}
    origin = data.get('origin')
    destination = data.get('destination')

    if not origin or not destination:
        return jsonify({'error': 'origin and destination required'}), 400

    try:
        r = requests.get(DIRECTIONS_URL, params={
            'origin':      f"{origin['lat']},{origin['lng']}",
            'destination': f"{destination['lat']},{destination['lng']}",
            'key':         config.GOOGLE_MAPS_SERVER_KEY,
            'mode':        'driving',
        }, timeout=10)
        directions = r.json()
    except requests.RequestException:
        return jsonify({'error': 'routing timeout'}), 504

    if directions.get('status') != 'OK':
        return jsonify({'error': 'no route found', 'details': directions.get('status')}), 422

    leg = directions['routes'][0]['legs'][0]
    encoded = directions['routes'][0]['overview_polyline']['points']

    stations = _get_ev_stations_along_route(encoded)

    return jsonify({
        'polyline':        encoded,
        'distance_text':   leg['distance']['text'],
        'duration_text':   leg['duration']['text'],
        'station_count':   len(stations),
        'stations':        stations,
    })


@app.post('/api/poi')
def poi():
    data = request.get_json(silent=True) or {}
    lat = data.get('lat')
    lng = data.get('lng')
    if lat is None or lng is None:
        return jsonify({'error': 'lat and lng required'}), 400

    try:
        r = requests.post(
            PLACES_NEARBY_URL,
            json={
                'includedTypes': ['restaurant', 'cafe', 'fast_food_restaurant', 'coffee_shop'],
                'maxResultCount': 5,
                'locationRestriction': {
                    'circle': {
                        'center': {'latitude': lat, 'longitude': lng},
                        'radius': 500,
                    }
                },
            },
            headers=_places_headers(
                'places.displayName,places.primaryTypeDisplayName,'
                'places.rating,places.regularOpeningHours.openNow,places.googleMapsUri'
            ),
            timeout=5,
        )
        places = r.json().get('places', [])
    except requests.RequestException:
        return jsonify({'places': []}), 200

    result = []
    for p in places:
        result.append({
            'name':     p.get('displayName', {}).get('text', ''),
            'type':     p.get('primaryTypeDisplayName', {}).get('text', ''),
            'rating':   p.get('rating'),
            'open_now': p.get('regularOpeningHours', {}).get('openNow'),
            'maps_url': p.get('googleMapsUri', ''),
        })
    return jsonify({'places': result})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=config.PORT, debug=False)
