import os
from dotenv import load_dotenv
load_dotenv()

GOOGLE_MAPS_JS_KEY     = os.environ.get('GOOGLE_MAPS_JS_KEY', '')
GOOGLE_MAPS_SERVER_KEY = os.environ.get('GOOGLE_MAPS_SERVER_KEY', '')
SECRET_KEY             = os.environ.get('SECRET_KEY', 'dev-secret-change-me')
PORT                   = int(os.environ.get('PORT', 5002))
