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
# Gunicorn >= 25.1 opens a control socket under $HOME/.gunicorn by default. KoloVibe never uses `gunicornc`, and
# the staging containers run as a non-root user on a read-only root filesystem, so the default path fails with
# EROFS. Disable it with Gunicorn's supported setting (the config-file form of --no-control-socket).
control_socket_disable = True

if settings.ENVIRONMENT == "staging":
    certfile = os.environ["KOLOVIBE_TLS_CERT_FILE"]
    keyfile = os.environ["KOLOVIBE_TLS_KEY_FILE"]
    ssl_version = ssl.PROTOCOL_TLS_SERVER
