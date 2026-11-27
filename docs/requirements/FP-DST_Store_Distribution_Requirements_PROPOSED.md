# FP-DST Google Play and Apple App Store distribution — requirements (PRD and SRS content)

**Status: APPROVED by the owner on 27 November 2026 at 12:26 UTC ("Approve all as recommended"), with the recommended option for every open choice. The file name keeps its original `_PROPOSED` suffix so links stay stable.** Approval covers development scope only. It does not approve a provider, an account, a value marked `[OWNER VALUE]`, live payments, live ads or store submission. Written in Phase 1 (27 November 2026). Indexed in [FP-000](FP-000_Full_Product_Requirements_Baseline.md). It defines what the Flutter apps (`apps/mobile`, Android id `com.kolovibe.kolovibe`, iOS deployment target 15.0) must satisfy to be distributed through Google Play and the Apple App Store, and how releases are controlled. **Submitting to either store, publishing a listing or releasing to the public is production publication and needs separate written owner authorization** (AGENTS.md). Nothing here creates a store account, chooses a legal entity, or decides an age rating or a legal question.

**[OWNER VALUE]** marks configuration or account facts with no default. Platform facts were checked on 27 November 2026 against the official pages cited in each row.

## 1. Repository state found (27 November 2026)

| Item | Found | Gap |
| --- | --- | --- |
| Android `targetSdk` | `flutter.targetSdkVersion` (Flutter default) | Must be pinned to the level Play requires (DST-R-001) |
| Android permissions | `INTERNET` only | `POST_NOTIFICATIONS` (FP-NT), `AD_ID` declaration decision (FP-GA) |
| iOS privacy manifest | No `PrivacyInfo.xcprivacy` in `Runner` | Required review (DST-R-011) |
| iOS usage strings | `NSPhotoLibraryUsageDescription` only | Camera and microphone strings if in-app capture is added; none for tracking (FP-GA GA-R-014) |
| Deletion web resource | `apps/policies/delete-account.md` rendered by `scripts/build_policy_site.py`; not hosted; email address placeholder | Hosting is an owner operations decision; address [OWNER VALUE] |
| Privacy policy and terms pages | Rendered from Identity's legal texts; "pending legal review" | Legal review (#165) before submission |

## 2. Google Play requirements

| ID | Requirement | Source | Acceptance criterion |
| --- | --- | --- | --- |
| DST-R-001 | New apps and updates target Android API level 36 from 31 August 2026 (Google lists an extension to 1 November 2026); `targetSdk` is pinned explicitly in `build.gradle.kts`, not left to the Flutter default | [Target API requirements](https://support.google.com/googleplay/android-developer/answer/11926878) | CI check reads the built AAB's target SDK and fails below the configured minimum [OWNER VALUE default 36] |
| DST-R-002 | Builds support 16 KB memory page sizes (required for apps targeting API 35 and above with native code; Google states updates must support it from 1 February 2027) | [Page sizes](https://developer.android.com/guide/practices/page-sizes) | Release AAB checked with the Android tooling for 16 KB alignment; app boots on a 16 KB emulator image |
| DST-R-003 | Release artefact is an Android App Bundle signed with an upload key; Play App Signing holds the app signing key; neither key nor its passwords are in Git or CI logs | Play Console | Keystore path and passwords come from CI secrets; secret scan passes |
| DST-R-004 | If the developer account is a personal account created after 13 November 2023, a closed test with at least 12 testers opted in for at least 14 continuous days is required before production access | [Testing requirements](https://support.google.com/googleplay/android-developer/answer/14151465) | Test record shows tester count and dates; not needed for an organization account (DST-D1) |
| DST-R-005 | Data safety form completed and matched to actual behaviour of the app and every SDK (FCM, Google Mobile Ads, video and image plugins), including the account deletion questions and the deletion URL | [Data safety and deletion](https://support.google.com/googleplay/android-developer/answer/13327111) | Data safety worksheet in the repo, reviewed against a network capture of a test build |
| DST-R-006 | Account deletion: an in-app path to request deletion of the account and data, **and** a working web resource that names the app and developer and explains how to request deletion; retention of any data kept is disclosed | Same | In-app path reachable from Settings within three taps; web page reachable without sign-in |
| DST-R-007 | Payments follow Play Payments policy (FP-PAY section 1): no Play Billing for live-event tickets; no steering to other payment methods for digital items | [Payments](https://support.google.com/googleplay/android-developer/answer/9858738) | Release checklist item signed by reviewer |
| DST-R-008 | User-generated content policy: in-app reporting, blocking, moderation and terms acceptance before posting are present (existing Moderation plus FP-CM) | Play UGC policy | Checklist with screen ids |
| DST-R-009 | Content rating questionnaire answered by the owner; ads declaration matches FP-GA (contains ads: yes once any build with ads ships to testers) | Play Console | Record of answers with date and person [OWNER VALUE] |
| DST-R-010 | Store listing links the developer website, privacy policy URL and support contact; the developer website root is where app-ads.txt is served before live ads (FP-GA GA-R-016) | Play Console, AdMob | Listing fields recorded in the release checklist |

## 3. Apple App Store requirements

| ID | Requirement | Source | Acceptance criterion |
| --- | --- | --- | --- |
| DST-R-011 | Privacy manifests: the app and every SDK on Apple's list that the app includes (Flutter, `video_player_avfoundation`, `image_picker_ios`, `url_launcher`, `path_provider`, `shared_preferences`, `share_plus`, FirebaseCore, FirebaseMessaging and the others present) ship a privacy manifest, and binary SDKs are signed; the app's own `PrivacyInfo.xcprivacy` declares required-reason API use | [Third-party SDK requirements](https://developer.apple.com/support/third-party-SDK-requirements/) | Xcode privacy report generated for the release archive and stored with the release record; required-reason API rules confirmed from Apple's privacy manifest documentation before Phase 10 (not read for this set) |
| DST-R-012 | App Privacy details completed, including third-party code practices; tracking declared only if tracking occurs (FP-GA says it does not in the first release) | [App privacy details](https://developer.apple.com/app-store/app-privacy-details/) | Answers worksheet reviewed against network capture |
| DST-R-013 | Privacy policy link in App Store Connect and inside the app (5.1.1(i)) | App Review Guidelines 5.1.1 | Link visible on sign-up and in Settings |
| DST-R-014 | Account deletion initiated inside the app; deletes the account and associated data the developer is not legally required to keep, including shared user content; works in every location; if completion is not immediate the person is told how long it takes and gets a confirmation (5.1.1(v)) | [Account deletion guidance](https://developer.apple.com/help/app-review/guideline-reference/5-1-1-account-deletion/) | Existing Decision C flow shows the expected duration [OWNER VALUE] and sends the completion notice (GD-12) |
| DST-R-015 | User-generated content (1.2): filtering of objectionable material, reporting with timely responses, blocking of abusive users, published contact information | App Review Guidelines 1.2 | Each mapped to screens and Moderation queues; response time target [OWNER VALUE] |
| DST-R-016 | Creator apps (1.2.1(a)): content above the app's age rating is identified and restricted using verified or declared age | Guidelines 1.2.1(a) | Age gate tests against Decision G age data |
| DST-R-017 | Push (4.5.4): the app works without push; no sensitive personal information in pushes; marketing pushes only after explicit in-app opt-in with an in-app opt-out | Guidelines 4.5.4 | FP-NT NT-R-006, NT-R-008, NT-D2 |
| DST-R-018 | Ads (2.5.18): ads only in the main app binary, suitable for the age rating, with a way to report inappropriate ads | Guidelines 2.5.18 | FP-GA GA-R-011, GA-R-013 |
| DST-R-019 | Payments (3.1): FP-PAY section 1; written App Review confirmation for tickets (3.1.3(e)) and ad purchases (3.1.3(g)) is attached to the submission record | Guidelines 3.1 | Confirmation stored before submission |
| DST-R-020 | Sign-in (4.8): KoloVibe's own email sign-in only, so 4.8 is not triggered; adding any third-party or social sign-in requires adding an option meeting 4.8 at the same time | Guidelines 4.8 | Checklist item; social sign-in absent |
| DST-R-021 | Distribution through TestFlight internal, then external testing, then phased release; APNs key and certificates stored as CI secrets | App Store Connect | Release record per build |

## 4. Release control (both stores)

| ID | Requirement | Acceptance criterion |
| --- | --- | --- |
| DST-R-030 | One version source: `pubspec.yaml` version and build number drive both stores; build numbers only increase | CI check |
| DST-R-031 | Staged rollout: Play staged percentages and Apple phased release, with steps [OWNER VALUE] | Release plan record |
| DST-R-032 | Server-side minimum supported version: the config route returns `min_supported_version` per platform; older apps show an update screen and make no other calls | Widget test with an old version |
| DST-R-033 | Remote kill switches per capability (ads, payments, uploads, comments) through the existing capabilities route, usable without a new release | Switch tests (FP-GA GA-R-012, FP-PAY PAY-R-018) |
| DST-R-034 | Crash and error reporting choice is recorded before release and declared in both store forms; no tool is added without the choice | Decision record (DST-D4) |
| DST-R-035 | Release checklist file per version in `docs/operations/releases/` lists every DST row with evidence links; any row without evidence blocks submission | Checklist completeness check |
| DST-R-036 | Store-facing environment points only at production endpoints; staging builds use a different bundle id suffix or flavour and never ship to public tracks | Flavour test |

## 5. Security

Signing keys, keystore passwords, App Store Connect API keys, APNs keys and Firebase service files are CI secrets; `google-services.json` and `GoogleService-Info.plist` for production are injected at build time, not committed. Store accounts use organization ownership with at least two administrators and MFA (DST-D1). Release builds strip debug logging of tokens and personal data.

## 6. Privacy

Store disclosures must match the data inventory (ADR-020) and the SDK list. A disclosure worksheet is regenerated whenever an SDK is added or upgraded, and the change review includes it.

## 7. Flutter screens (no new range; reuse existing ids where they exist)

Update-required screen; in-app deletion entry (existing Decision C screens); privacy policy and terms links (existing); ad privacy choices entry (FP-GA M-461); notification permission pre-prompt (FP-NT M-423). New frames, if any, follow #306.

## 8. Failure scenarios

Review rejection (record the guideline cited, fix, resubmit; no workaround that changes payment rails without owner decision); target API deadline missed (Play blocks updates: CI gate DST-R-001 prevents it); expired APNs key or certificate (push fails, alert); compromised upload key (Play upload key reset procedure documented); bad release (halt staged rollout, raise `min_supported_version` only for security issues).

## 9. Choices still open

| Choice | Options | Recommendation |
| --- | --- | --- |
| DST-D1 Developer account type and owner | (a) organization accounts on both stores under the owner's legal entity [OWNER VALUE]; (b) personal accounts | (a): business assets, and Play's 12-tester closed test rule applies only to new personal accounts |
| DST-D2 Hosting of the policy and deletion pages and the developer website root | Owner operations decision (apps/policies README) | Host the existing static site on the KoloVibe domain; add app-ads.txt there only when live ads are authorized |
| DST-D3 Age rating answers and minimum age | Owner and legal review | Owner supplies; development assumes the most restrictive answers |
| DST-D4 Crash reporting | (a) none in first release; (b) Firebase Crashlytics (on Apple's SDK list; needs disclosure) | (b) once disclosures are updated, because release triage needs it |
| DST-D5 Store payment confirmations | Ask App Review and Play policy support in writing (FP-PAY PAY-D2 to PAY-D4) | Do this before Phase 10 submission |

## 10. Traceability

FP-MB-01, FP-MB-02, FP-PV rows; Decisions C and G; owner rulings of 25 and 26 November 2026 on policy and deletion pages; GD-12; issues #307, #324, #310.
