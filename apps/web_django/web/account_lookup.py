"""Administrator-only account lookup by full email address, shared by every console page that picks a person.

One implementation of the rules: a full address is required, only the owning service decides whether it matches,
the answer is validated and the failure messages are fixed copy that never echoes the gateway.
"""

from . import views
from .admin_contracts import valid_candidate

MESSAGES = {404: "No account with that email can be {verb}. The person must register in the app first.",
            429: "Too many lookups. Try again later.",
            403: "Only administrators can look up accounts.",
            400: "Enter the person's full email address."}
UNAVAILABLE = "Account lookup is unavailable right now."


def find(request, email, *, verb="used"):
    """Return ("found", candidate, 200), ("expired", None, 401) or ("error", message, http status to answer with)."""
    email = email.strip()
    if not 3 <= len(email) <= 254 or "@" not in email:
        return "error", MESSAGES[400], 400
    status, found = views._api("/admin/accounts/lookup", method="POST", data={"email": email}, token=request.gateway_token)
    if status == 401:
        return "expired", None, 401
    if status == 200 and valid_candidate(found):
        return "found", found, 200
    return "error", MESSAGES.get(status, UNAVAILABLE).format(verb=verb), status if status in MESSAGES else 503
