"""Step-up for sensitive owner actions (Decision G; BZ-R-036).

Identity owns the one step-up mechanism. The person obtains a purpose-bound, single-use proof from Identity; the
Gateway consumes it at Identity with the same session and attests only the verified purpose and resource in the
signed envelope. This module never sees a password or a proof: it checks that the attestation names exactly the
purpose and the business the operation acts on. Anything else (no proof, another purpose, another business) is
refused, so a proof for one business or action cannot authorize another.
"""
from .errors import ApiError


def require(ctx, purpose, resource_id):
    if ctx.step_up != {"purpose": purpose, "resource_id": str(resource_id)}:
        raise ApiError(403, "Step-up authentication is required", "step_up_required")
