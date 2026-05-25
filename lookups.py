# Google Places connector type enum → display label
CONNECTOR_LABELS = {
    'EV_CONNECTOR_TYPE_CCS_COMBO_1':  'CCS',
    'EV_CONNECTOR_TYPE_CCS_COMBO_2':  'CCS2',
    'EV_CONNECTOR_TYPE_CHADEMO':      'CHAdeMO',
    'EV_CONNECTOR_TYPE_J1772':        'J1772',
    'EV_CONNECTOR_TYPE_TESLA':        'NACS',
    'EV_CONNECTOR_TYPE_TYPE_2':       'Type 2',
    'EV_CONNECTOR_TYPE_NACS':         'NACS',
    'EV_CONNECTOR_TYPE_OTHER':        'Other',
}

# Network name substrings → access metadata
# Matched against station displayName (case-insensitive, first match wins)
NETWORK_PATTERNS = [
    ('electrify america', {
        'app_required': False,
        'app_name': 'Electrify America',
        'app_android': 'https://play.google.com/store/apps/details?id=com.ea.evowner',
        'note': 'Credit card tap or app',
    }),
    ('tesla', {
        'app_required': True,
        'app_name': 'Tesla',
        'app_android': 'https://play.google.com/store/apps/details?id=com.teslamotors.tesla',
        'note': 'Tesla app required; non-Tesla vehicles need app + payment linked',
    }),
    ('chargepoint', {
        'app_required': False,
        'app_name': 'ChargePoint',
        'app_android': 'https://play.google.com/store/apps/details?id=com.coulombtech',
        'note': 'App, RFID card, or credit card',
    }),
    ('evgo', {
        'app_required': False,
        'app_name': 'EVgo',
        'app_android': 'https://play.google.com/store/apps/details?id=com.evgo.evgo',
        'note': 'Credit card tap, app, or QR code',
    }),
    ('blink', {
        'app_required': False,
        'app_name': 'Blink Charging',
        'app_android': 'https://play.google.com/store/apps/details?id=com.blinknetwork.blink',
        'note': 'App recommended; credit card accepted at most stations',
    }),
    ('shell recharge', {
        'app_required': False,
        'app_name': 'Shell Recharge',
        'app_android': 'https://play.google.com/store/apps/details?id=com.shell.android.shellev',
        'note': 'App or credit card',
    }),
    ('rivian', {
        'app_required': True,
        'app_name': 'Rivian',
        'app_android': 'https://play.google.com/store/apps/details?id=com.rivian.android.consumer',
        'note': 'Rivian vehicles only (non-Rivian access limited)',
    }),
    ('flo', {
        'app_required': False,
        'app_name': 'FLO',
        'app_android': 'https://play.google.com/store/apps/details?id=com.flo.charging',
        'note': 'App or credit card',
    }),
    ('francis energy', {
        'app_required': False,
        'app_name': 'Francis Energy',
        'app_android': 'https://play.google.com/store/apps/details?id=com.francisenergy.app',
        'note': 'Credit card or app',
    }),
    ('evcs', {
        'app_required': False,
        'app_name': 'EVCS',
        'app_android': 'https://play.google.com/store/apps/details?id=com.evcs.app',
        'note': 'Credit card or app',
    }),
    ('volta', {
        'app_required': False,
        'app_name': None,
        'app_android': None,
        'note': 'Free at retail locations; plug in and go',
    }),
]

_UNKNOWN_ACCESS = {
    'app_required': False,
    'app_name': None,
    'app_android': None,
    'note': '',
}


def get_network_access(station_name: str) -> dict:
    name_lower = (station_name or '').lower()
    for pattern, info in NETWORK_PATTERNS:
        if pattern in name_lower:
            return info
    return _UNKNOWN_ACCESS
