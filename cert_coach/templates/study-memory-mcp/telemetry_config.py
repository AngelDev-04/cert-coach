"""Deployed adoption-telemetry endpoint, shipped with the Power.

DevOps fills these two constants in once, after deploying the ingest API, and re-shares the
Power. Colleagues then configure nothing: no environment variable, no ``mcp.json`` edit, no
config file to drop in. That is the whole point of committing them here.

They cannot live in ``mcp.json``. ``scripts/validate_project.py`` rejects any ``${`` in that
file's args or env values, because Kiro never expands ``${PLUGIN_ROOT}`` and expands real
environment variables only after the user approves them via ``kiroAgent.mcpApprovedEnvVars``.
A committed Python constant sidesteps both problems.

While ``TELEMETRY_ENDPOINT`` is empty the Power ships inert and transmits nothing, so an
un-deployed checkout behaves exactly as it did before telemetry existed.

The token is a spam gate, not a security boundary: anyone who can read this repository can
read it. That is acceptable only because the endpoint is write-only and the payload carries
no study performance data (see ``docs/telemetry-design.md``). Keep this repository private
and throttle the API Gateway stage.
"""

from __future__ import annotations

#: Full URL of the ingest route, e.g.
TELEMETRY_ENDPOINT = ""

#: Shared bearer token checked by the ingest Lambda.
TELEMETRY_TOKEN = ""
