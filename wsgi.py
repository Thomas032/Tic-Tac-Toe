from app import app
import eventlet.wsgi

eventlet.wsgi.server(eventlet.listen(('', 8000)), app)
