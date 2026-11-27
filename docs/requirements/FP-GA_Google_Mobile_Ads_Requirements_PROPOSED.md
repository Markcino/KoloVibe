# FP-GA Google mobile advertising — requirements (PRD and SRS content)

**Status: PROPOSED for owner approval.** Written in Phase 1 (27 November 2026). Indexed in [FP-000](FP-000_Full_Product_Requirements_Baseline.md). Scope comes from Decision I and PRD-F11: Google Mobile Ads in the Flutter apps with **test placements only** until the owner separately authorizes live advertising. Direct sponsorship and the Advertising service remain governed by [AD](AD-Requirements_PRD_SRS_PROPOSED.md), whose section 1 excludes network SDKs; this set is the separately approved place where the Google Mobile Ads SDK is allowed, and AD's exclusion stays true for the Advertising service itself.

**[OWNER VALUE]** marks configuration with no default. No ad unit id, publisher id, revenue term or account is invented here. Live ad units, live serving and any revenue claim need separate written owner authorization (AGENTS.md: development approval does not authorize live advertising).

Platform facts checked on 27 November 2026 against Google's official pages: [AdMob Flutter privacy and UMP](https://developers.google.com/admob/flutter/privacy), [ad serving modes](https://developers.google.com/admob/flutter/privacy/ad-serving-modes), [GDPR guidance](https://developers.google.com/admob/flutter/privacy/gdpr), [test ads](https://developers.google.com/admob/flutter/test-ads), AdMob help on [invalid activity](https://support.google.com/admob/answer/2753860), [app-ads.txt](https://support.google.com/admob/answer/9363762), [Families and child-directed treatment](https://support.google.com/admob/answer/6223431) and [ad placement policy](https://support.google.com/admob/answer/6128543); Apple App Review Guidelines 2.5.18, 3.2.2 and 5.1.2 and the App Privacy details page.

## 1. Scope

**In:** the `google_mobile_ads` Flutter plugin; Google's User Messaging Platform (UMP) consent flow; a small set of placements decided by configuration; test ad units and test devices; age-based ad treatment; a report-an-ad path; consent and tracking disclosures; server-side control of whether ads show at all; app-ads.txt preparation.

**Out:** live ad units; mediation networks; rewarded ads (Points or any reward for ad interaction is forbidden, FR-016; AdMob forbids incentives to click); ads in notifications, widgets or app extensions (Apple 2.5.18); ads to accounts under the age threshold where policy requires none; any ad shown inside a video before or during playback; ad revenue in creator payouts (Finance has no ad network revenue source until separately approved).

## 2. Ownership

| Component | Owner |
| --- | --- |
| Placement configuration, kill switch, ad unit ids per platform | Advertising service config, delivered through the existing `capabilities`/config route; ad unit ids are [OWNER VALUE] and the build ships Google's published test ids |
| Consent state for ads | UMP SDK on the device; KoloVibe's own consent record (GD-06, Identity) stores the person's KoloVibe advertising choice and the UMP status for audit, not the TC string |
| Age signal | Identity (declared or verified age, Decision G and creator rules) |
| Ad reports | Moderation (Report with `target_type=ad`, reusing the FP-CM extension) |

## 3. Functional requirements

| ID | Requirement | Pri | Acceptance criterion |
| --- | --- | --- | --- |
| GA-R-001 | The app calls `ConsentInformation.requestConsentInfoUpdate` on every launch, then `loadAndShowConsentFormIfRequired`; no ad request is made while `canRequestAds()` is false | M | Integration test with UMP debug geography EEA: no ad request before consent |
| GA-R-002 | A privacy options entry point ("Ad privacy choices") is shown in settings whenever `getPrivacyOptionsRequirementStatus()` is `required`, and opens `showPrivacyOptionsForm` | M | Widget test for both status values |
| GA-R-003 | For users in the EEA, UK and Switzerland a Google-certified CMP that integrates with the IAB TCF is used; Google's UMP is the recommended CMP (GA-D1) | M | Release checklist records the CMP and its certification |
| GA-R-004 | Ads are served in the mode the consent allows (personalised, non-personalised or limited ads); KoloVibe never overrides the UMP outcome | M | Test matrix over consent outcomes |
| GA-R-005 | Age treatment: an account under the age threshold [OWNER VALUE] `ads.min_age` or with unknown age gets **no ads** in the first release; if the owner later allows ads to such accounts, every request sets `tagForUnderAgeOfConsent` / child-directed treatment and `maxAdContentRating` G as Google's Families guidance requires | M | Request configuration test per age state |
| GA-R-006 | All builds other than a release build authorized for live ads use Google's published test ad unit ids (banner Android `ca-app-pub-3940256099942544/6300978111`, iOS `ca-app-pub-3940256099942544/2934735716`; other formats from the same page) | M | Build check fails a non-authorized build that contains a non-test unit id |
| GA-R-007 | Physical test devices are registered with `RequestConfiguration.testDeviceIds` from build configuration; emulators are test devices automatically; team members never click live ads | M | Test plan instruction; config check |
| GA-R-008 | Placements are configuration: allowed formats in the first release are banner and native in the feed between items, never over video controls, never inside a video, and at most one in [OWNER VALUE] `ads.feed_spacing` items | M | Layout tests: ad never overlaps playback controls or navigation |
| GA-R-009 | Interstitial and app-open formats are off in the first release; if enabled later they need a visible close control (Apple 2.5.18) and frequency caps [OWNER VALUE] | S | Flag test |
| GA-R-010 | No reward, Points, unlock or ranking is ever tied to viewing or clicking an ad, and the app never prompts users to click ads (AdMob invalid activity; Apple 3.2.2(iii)) | M | Static check: ad callbacks call no Points or Engagement code |
| GA-R-011 | Every ad has a "Report this ad" action (Apple 2.5.18) that records the ad's response id, placement and reason as a Moderation report, and hides that ad for the reporter | M | Widget and API test |
| GA-R-012 | Server kill switch `ads.enabled` (global and per platform) is read at launch and on resume; off means no SDK initialisation and no request | M | Switch test, including first launch offline (default off) |
| GA-R-013 | Ads never show on: sign-in and sign-up, account deletion, privacy and policy screens, payment screens, moderation and appeal screens, creator upload, and the console | M | Route allowlist test |
| GA-R-014 | iOS App Tracking Transparency: no ATT prompt and no IDFA use in the first release; requests are made without tracking. If the owner later wants tracking, an ATT prompt before any tracking and a matching App Privacy declaration are required | M | iOS build has no `NSUserTrackingUsageDescription` unless enabled; privacy details match |
| GA-R-015 | Android advertising ID: the `AD_ID` permission declaration and Play Data safety answers match actual SDK behaviour; for child or unknown-age accounts the ad ID is not used | M | Manifest check; Data safety record |
| GA-R-016 | app-ads.txt: the file content is prepared from the publisher id [OWNER VALUE] and served at the root of the developer website listed in both store listings, before live serving | M (before live) | Checklist item; Google's text read for this set did not state the file is mandatory, so it is treated as required by KoloVibe policy |
| GA-R-017 | The app performs normally when the SDK fails to initialise, consent cannot load, or no fill is returned: the placement collapses, no blank space, no retry storm (retry with backoff, cap [OWNER VALUE]) | M | Offline and no-fill tests |
| GA-R-018 | Ad impressions are not counted as KoloVibe engagement or qualified views and never enter the Points or Finance ledgers | M | Contract test |

## 4. Security and privacy

- The SDK is a third party that collects data: declare it in Play Data safety (advertising ID, app interactions, diagnostics, approximate location as the SDK documents) and in Apple App Privacy details, including the practices of third-party code, as Apple's page requires.
- Apple's third-party SDK list read on 27 November 2026 did not list `GoogleMobileAds`; that is not an exemption. The iOS build must include Google's own privacy manifest from the current SDK, and the release checklist reviews Xcode's privacy report (FP-DST).
- No KoloVibe personal data (account id, email, age, follows) is passed to the ad SDK as targeting.
- Sensitive categories are blocked in the AdMob console [OWNER VALUE], recorded with the date and the person who set them.

## 5. API and configuration

No new public API. The existing configuration route returns: `ads.enabled`, `ads.platforms`, `ads.placements[]` (id, format, unit id, spacing), `ads.min_age`. Console: `PUT /api/v1/admin/ads/network-config` (administrator, MFA, audited). Ad reports use `POST /api/v1/reports` with `target_type=ad`.

## 6. Event contracts

`kolovibe.moderation.report.created.v1` with `target_type=ad` (catalogue #305). No impression or click events are sent to KoloVibe servers in the first release.

## 7. Flutter screens and components (M-460 to M-469; Figma frames first, #306)

M-460 consent form host (UMP); M-461 "Ad privacy choices" settings entry; M-462 feed banner slot; M-463 feed native slot; M-464 report-this-ad sheet; M-465 ad hidden confirmation.

## 8. Failure scenarios

Consent form fails to load (no ads, retry next launch); consent withdrawn (requests stop or switch to the permitted mode at once); kill switch turned off mid-session (slots removed on next resume); policy strike in AdMob (switch off and record an incident); test unit id missing from config (no ad, logged once).

## 9. Non-functional

Feed scroll frame rate with ads within 5% of the same feed without ads on the reference test devices; SDK initialisation does not block first frame (initialise after first frame).

## 10. Choices still open

| Choice | Options | Recommendation |
| --- | --- | --- |
| GA-D1 Consent platform | (a) Google UMP (certified, TCF); (b) another certified CMP | (a) UMP |
| GA-D2 AdMob account ownership | (a) the owner's organization account; (b) personal | (a), same reason as NT-D1 |
| GA-D3 Ads to minors and unknown-age accounts | (a) none in the first release; (b) child-directed treatment | (a) none |
| GA-D4 Formats in the first release | (a) banner and native in feed only; (b) add interstitial | (a) |
| GA-D5 Live activation | Separate owner authorization after Phase 10 store review | Keep test units until authorized |

## 11. Traceability

FP-GA-01; PRD-F11; DR-AD-36; Decision I; GD-06; issues #307, #321 to #323.
