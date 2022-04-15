from app import app
import eventlet.wsgi
import os

eventlet.wsgi.server(eventlet.listen((os.environ.get('PORT', '5000'), 5000)), app)
