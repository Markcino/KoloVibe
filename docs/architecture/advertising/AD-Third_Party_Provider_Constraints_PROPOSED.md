# Third-party advertising provider constraints (proposed)

**Status: PROPOSED — evidence summary, not an approval, not a promise.** 25 November 2026. Phase 8 integrates **no** network. This records what is known, what was checked, and what the owner must verify against the provider's current documents before any approval request. Provider terms and country lists change; nothing here substitutes for reading them at application time. **Provider approval is never assumed or promised.**

## 1. Why this is separate from the direct-sold build

The first-party design serves reviewed direct campaigns from the `ads` service. AdMob or any network is a *different* system: it brings its own SDK, identifiers, consent requirements, review and payment terms. It would sit behind a `NetworkAdapter` interface (request, validate, report) that is documented in ADR-AD-001 and **not implemented or registered**. PRD §11 already says publisher and app approval "are not guaranteed".

## 2. What was checked on 25 November 2026 (web search; to be re-verified)

| Question | Finding | Confidence |
| --- | --- | --- |
| Can a Liberian publisher sign up for AdMob? | A Google AdMob help page listing places where you can register ([support.google.com/admob/answer/16451422](https://support.google.com/admob/answer/16451422?hl=pl), Polish version) includes Liberia | Moderate: found in a localized page; confirm in English at application time |
| Can AdMob pay a publisher in Liberia? | **No payment-country table for Liberia was found.** Results mention sanctions compliance ([AdMob help](https://support.google.com/admob/answer/6163675)) naming other regions, not Liberia, and Google Play merchant registration lists Liberia (USD) ([Play help](https://support.google.com/googleplay/android-developer/answer/9306917)); neither answers AdMob payouts | **Unverified; blocker for any revenue claim** |
| Is `app-ads.txt` required? | Google calls it **recommended, not required**; it lets AdMob and others verify app ownership; the developer **website must be linked in the store listing** and the file placed at that site's root ([AdMob help](https://support.google.com/admob/answer/9363762), [developer guide](https://developers.google.com/admob/ios/app-ads)) | High |
| Native ad labelling and placement | Native ads need an attribution ("Ad", "Advertisement" or "Sponsored"), must be clearly separated from app content and must not overlap it; overlapping can cause accidental clicks and invalid traffic ([native ad policy](https://support.google.com/admob/answer/6329638), [validator](https://developers.google.com/admob/ios/native/validator)) | High |
| Test ads | A native validator runs on test ads only; live requests do not use it | High |
| Consent (User Messaging Platform) and personalised-ad rules | **Not verified** by this search; consent requirements for the EEA, UK and Switzerland exist, and applicability to Liberian users, app stores and children is unconfirmed | **Unverified** |
| AdSense | AdSense is for websites. KoloVibe has no website (DR-BZ-21), so AdSense is **not applicable** unless that decision changes | Reasoned, to be confirmed |

## 3. Constraints that conflict with current decisions

| Constraint | Conflict | Options for the owner |
| --- | --- | --- |
| Store listing must link a developer website for `app-ads.txt` | DR-BZ-21 says no public website | (a) Do not use `app-ads.txt` (allowed, with spoofing risk); (b) a minimal static, non-interactive file host that serves only that file, as an explicit exception; (c) no network ads at all |
| SDK collects or uses advertising identifiers and sets cookies/IDs | Policies §5 forbids advertising IDs and behavioural data | Network ads would need a different consent, privacy notice, store data-safety declaration and iOS tracking-permission treatment; a separate privacy decision |
| SDK network calls from the app to Google domains | Mobile is currently allowed to talk to the KoloVibe API only | Egress, certificate and proxy implications; network-policy change |
| New dependency (`google_mobile_ads`) | Dependency review and pinning (`dependency-and-security.md`) | Supply-chain review; exact version pin |
| Provider-controlled creatives | Our creative-review policy cannot apply to network ads | Rely on provider policy; add category blocking controls and a report path |
| Ad content in a feed of Liberian creators | Brand-safety and prohibited-category controls differ | Configure category blocks in the provider console |
| Revenue and payouts | Payment eligibility unverified; FR-016 bars passing network revenue to viewers | Finance review; PRD R4 rules |

## 4. Evidence the owner should assemble before asking for network approval

1. AdMob account eligibility and **payment country support for Liberia**, confirmed with Google in writing.
2. Publisher policy fit for the app (user-generated video content), including the content policies for UGC and the "app must be live in a store" requirement.
3. A decision on the website question (§3 first row).
4. Consent management approach and legal review for Liberian users and minors; store data-safety and iOS privacy declarations.
5. Dependency review of the SDK, network egress change and a test-ads-only plan with test device ids.
6. A funded model for any revenue use, kept separate from Points (FR-016).

## 5. What Phase 8 delivers regarding networks

Nothing integrated. It delivers: the adapter interface description, a build **guard** that fails if a network SDK dependency or adapter is added without an approval constant, a placement design in which a network slot would be a *different, labelled source* inside the same placement, and this checklist.
