# DRY-01 — One gateway error response

**Type:** behaviour-preserving refactor. **Baseline reference:** Phase 0 DRY analysis D-C / D-G.

## Duplication verified
Five gateway modules (`analytics`, `creator_onboarding`, `media`, `moderation`, `pilot_points`) each defined the same function, `JsonResponse({"detail": detail}, status=status)`, byte for byte. The body shape is part of the public contract (DOC-205 error bodies), so five copies are five places it could drift.

## Change
- New `services/gateway/service/responses.py` with `error_response(detail, status)`.
- The five modules import it under their existing local name (`_error`, and `error` in `pilot_points`), so no call site changed and no import elsewhere breaks.
- Net: 5 definitions removed, 1 added.

## Deliberately not done
- **Owning services keep their own helpers** (`content`, `creators`, `moderation`, `identity`, …). They are separate deployables with separate authorization and databases; sharing application code across them is what Phase 1 rules forbid.
- Inline `JsonResponse({"detail": ...})` expressions elsewhere in the gateway (about 60 sites) are left as they are; converting them is mechanical but a larger diff with no behavioural benefit now. They can adopt `error_response` as modules are touched.
- `accounts._json` has different semantics (204 handling) and is untouched.

## Evidence
Gateway suite 183 tests OK, identical to the pre-change run. No response body, status or header changed.
