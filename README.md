# truehair-ai
An AI-powered hairstyle visualization platform that helps users to explore hairstyles and connect with local stylists.

## IRB compliance — logging

Per IRB sections 2.1 and 6.5, client IP addresses must be stripped from application and infrastructure logs. This is implemented at two layers:

- **Gunicorn access logs**: `Procfile` sets a custom `--access-logformat` that omits `%(h)s` (remote host). Only HTTP method, path, status, response size, latency, and the Heroku `X-Request-Id` correlation ID are logged.
- **Flask / WSGI**: `app/__init__.py` wraps the WSGI app in `werkzeug.middleware.proxy_fix.ProxyFix(..., x_for=0, x_proto=1, x_host=1)`. With `x_for=0`, Flask ignores the `X-Forwarded-For` header, so `request.remote_addr` resolves to Heroku's internal router IP rather than the client's public IP. `x_proto` and `x_host` remain enabled so HTTPS and host detection still work for `url_for(..., _external=True)`.
- **Request bodies**: no code path passes `request.data`, `request.files`, `request.form`, or `request.get_json()` into a logger. Error handlers log only exception messages and stack traces.

### Known limitation — Heroku router logs

Heroku's own router logs (emitted by `heroku[router]`) include the client IP in the `fwd=` field, and this cannot be stripped at that layer without a custom log drain. Mitigations:

- Heroku log retention is ~1 week without a logging addon.
- These logs are used only for operational debugging and are not queried by the research team as part of any analysis.

This nuance should be surfaced to the IRB contact if further clarification is required.