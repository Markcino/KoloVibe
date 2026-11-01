import os
import ssl

from django.conf import settings

from staging_runtime.wsgi import application

bind = "0.0.0.0:8000"
workers = 2
timeout = 30
graceful_timeout = 30
accesslog = None
errorlog = "-"
forwarded_allow_ips = ""
secure_scheme_headers = {}
preload_app = False

if settings.ENVIRONMENT == "staging":
    certfile = os.environ["KOLOVIBE_TLS_CERT_FILE"]
    keyfile = os.environ["KOLOVIBE_TLS_KEY_FILE"]
    ssl_version = ssl.PROTOCOL_TLS_SERVER
