"""Rate-limit constants for ``/auth/token-exchange`` and the bound
refresh path.

Four dimensions are throttled, per the plan's "O2" requirement:

- per ``client_id`` -- defends against a single misbehaving client
- per source IP -- defends against distributed abuse (note: a single
  br.AI.n instance is a single IP, so this dimension on its own is
  weak; do not size the per-client / per-org limits assuming this
  catches anything)
- per ``(client_id, hashed_subject_email)`` -- defends per-user
  credential stuffing
- per ``organization_id`` -- caps the org's exchange budget so a
  single client cannot saturate it by enumerating subject emails

The limits below are starting budgets; revisit once a real
integration is live and we have traffic shape to size against. The
rates are deliberately higher than the 10/min SSO callback budget
because token exchange is server-to-server and bursts of legitimate
traffic (e.g. cold-start of a worker pool) are expected.
"""

from __future__ import annotations

#: Per ``client_id`` -- the most common throttle dimension. A
#: misbehaving integration retries at most this fast before being told
#: to back off.
TOKEN_EXCHANGE_PER_CLIENT_RATE_LIMIT = "60/minute"

#: Per source IP -- weak for server-to-server flows (single IP per
#: integration), so kept generous on purpose.
TOKEN_EXCHANGE_PER_IP_RATE_LIMIT = "120/minute"

#: Per (client_id, hashed_subject_email). Tighter than per-client
#: because a credential-stuffing burst would target one or a few user
#: addresses very quickly.
TOKEN_EXCHANGE_PER_CLIENT_USER_RATE_LIMIT = "30/minute"

#: Per organization_id -- the global cap that prevents one client
#: from saturating the org's exchange budget by enumerating subject
#: emails.
TOKEN_EXCHANGE_PER_ORG_RATE_LIMIT = "240/minute"

__all__ = [
    "TOKEN_EXCHANGE_PER_CLIENT_RATE_LIMIT",
    "TOKEN_EXCHANGE_PER_CLIENT_USER_RATE_LIMIT",
    "TOKEN_EXCHANGE_PER_IP_RATE_LIMIT",
    "TOKEN_EXCHANGE_PER_ORG_RATE_LIMIT",
]
