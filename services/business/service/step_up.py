"""Step-up authentication for sensitive owner actions (contact change, closure, ownership transfer, staff removal).

The approved design (BZ-R-036) requires a fresh, purpose-bound proof. Identity cannot yet issue or verify one
for other services (prerequisite P6B-04, not approved), so this hook FAILS CLOSED: the guarded operations refuse
every caller until Identity provides the capability and `verify` is implemented. Nothing weaker is substituted.
"""
from .errors import ApiError


def require(actor, purpose):
    raise ApiError(403, "Step-up authentication is required and is not available yet", "step_up_unavailable")
