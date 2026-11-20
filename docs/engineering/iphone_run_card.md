# Physical iPhone run card

For the person holding the iPhone. Companion to [iphone_e2e_checklist.md](iphone_e2e_checklist.md) (steps, expected results, endpoints, blank Result column). **No result in either file has been observed on a device.** Leave every Result cell blank until it is.

## 1. Build commit

| Item | Value |
| --- | --- |
| Branch | `mobile/home-m017-design-audit` ([PR #96](https://github.com/Markcino/KoloVibe/pull/96)) |
| Commit at the time this card was written | `da5158877cfd82f6ad25fa25945e260eef4d11dd` |
| Rule | Build from the **current head** of that branch and write `git rev-parse HEAD` in the checklist header. If the head moved, the card’s commit is stale. |
| Not in that commit | The CI repairs in [PR #98](https://github.com/Markcino/KoloVibe/pull/98); they touch no mobile code. |

```bash
git fetch origin mobile/home-m017-design-audit
git checkout mobile/home-m017-design-audit
git rev-parse HEAD
cd apps/mobile
flutter --version          # expect Flutter 3.47.8
flutter pub get --enforce-lockfile
flutter analyze && flutter test
```

## 2. Run on the iPhone

Prerequisites (from [apps/mobile/README.md](../../apps/mobile/README.md#run-on-a-physical-iphone)): Xcode with the iPhone’s iOS version, the phone trusted and in Developer Mode, a signing team set for `Runner`, the app run once from Xcode.

```bash
cd apps/mobile
flutter devices                      # note the iPhone's id
flutter run --release -d <device-id> \
  --dart-define=KOLOVIBE_API_URL=https://mobile-api.cabetechs.shop/api/v1
```

Use a **release** build. The gateway URL must be HTTPS and end in `/api/v1`; debug builds also accept loopback HTTP, which is not what is being tested. Write the exact URL as built in the checklist header.

## 3. What each section needs

| Need | Meaning |
| --- | --- |
| Device | Only a physical iPhone can answer it (real video decode, keyboard, safe areas, force-close, Airplane mode, Link Conditioner) |
| Tester account | A verified viewer account (`VIEWER-1`, `VIEWER-2`), or a mailbox for `NEW-VIEWER` |
| Creator | An approved creator with verified email (`CREATOR-1`, `CREATOR-2`) |
| Reviewer | Operator-side API access with MFA (moderation decisions, creator approval) |
| Real upload | A genuine MP4 under 50 MB on the phone |
| Operator | A person with server access (revoke a session, force 403 / 429 / 503, compatibility policy, audit rows) |

| Checklist rows | Device | Tester acct | Creator | Reviewer | Real upload | Operator |
| --- | --- | --- | --- | --- | --- | --- |
| A1–A5 sign-up, verify (mailbox) | yes | `NEW-VIEWER` | | | | |
| A6–A8 duplicate, wrong password, sign-in | yes | `VIEWER-1` | | | | |
| A9 SEC-05 force-close restore | yes | `VIEWER-1` | | | | |
| A10 password reset | yes | `VIEWER-1` (mailbox) | | | | |
| A11 offline recovery | yes | `VIEWER-1` | | | | |
| A12 sign out and token rejection | yes | `VIEWER-1` | | | | yes |
| B1–B9 Home | yes | `VIEWER-1` | `CREATOR-2` has a published video | | | |
| C1–C5 Following, Explore, search | yes | `VIEWER-1` | `CREATOR-2` | | | |
| D1–D3, D6 playback, watch events | yes | `VIEWER-1` | `CREATOR-2` video | | | |
| D4–D5 unavailable and restricted video | yes | `VIEWER-1` | | | | yes (ids) |
| E1–E4 like, follow | yes | `VIEWER-1`, `VIEWER-2` (second device or session) | `CREATOR-2` | | | |
| E5–E7 failed follow, signed-out, share | yes | `VIEWER-1` | `CREATOR-2` | | | |
| F1 become a creator | yes | `VIEWER-1` | | | | |
| F2–F6 studio, upload, publish | yes | | `CREATOR-1` | yes (approve) | yes | |
| F7 Lone Stars | yes | | `CREATOR-1` | | | yes (to produce ledger entries) |
| F8–F9 report, offline submit | yes | `VIEWER-1` | | | | |
| F10 removal notice and appeal (M-076, M-078) | yes | | `CREATOR-1` | yes (remove, decide appeal) | | |
| G1–G5 settings and sessions | yes | `VIEWER-1`, second device for G3 | | | | |
| G6–G7 forced errors, compatibility | yes | `VIEWER-1` | | | | yes |
| H1–H6 layout, text size, keyboard | yes | `VIEWER-1` | `CREATOR-1` | | | |

## 4. Staging state observed from this computer (not from a phone)

Read-only requests on 20 November 2026 returned HTTP 200 over valid TLS: `GET /app/compatibility`, `GET /videos?sort=trending` and `GET /creators/search?q=a`. Trending and creator search returned **empty lists**, so Home will show its empty states until a video is published. Nothing authenticated was tried; no test account was available.

## 5. Recording

Fill the checklist’s record header and Result column on the device run only. For each FAIL attach a screenshot or recording reference and open a defect. Do not put credentials, codes, tokens or playback URLs in any record.
