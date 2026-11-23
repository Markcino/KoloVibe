# Physical Android end-to-end checklist (mobile design and live API)

Status: **not yet run on a device.** Nothing in this file has been executed on an Android phone. Every Result cell is blank on purpose. Widget tests, `flutter analyze` and simulator or emulator runs do **not** count as device acceptance, and no result may be written here by anyone who did not hold the device.

Companion to [iphone_e2e_checklist.md](iphone_e2e_checklist.md) (same sections A–H, same test-account labels, same endpoints) and [iphone_run_card.md](iphone_run_card.md). Use this file for the Android-specific build, behaviours and risks; use the iPhone checklist for the step-by-step rows, replacing "iPhone" with the Android device and reading the Android notes below. Rows marked **SEC** also gate security sign-off.

## 1. Build under test

```bash
git fetch origin && git checkout <commit-under-test> && git rev-parse HEAD      # write the full SHA in the record header
cd apps/mobile
flutter --version            # write the exact version; CI is pinned to the version in .github/workflows/ci_cd.yml
flutter pub get --enforce-lockfile
flutter analyze && flutter test
flutter devices              # the Android device must be listed (USB debugging on, computer trusted)
flutter run --release -d <device-id> \
  --dart-define=KOLOVIBE_API_URL=https://mobile-api.cabetechs.shop/api/v1
```

Rules: a **release** build only (debug builds accept loopback HTTP, which is not what is being tested); the URL must be HTTPS and end in `/api/v1`; sign with the team's release or internal-testing key, never a shared debug key, for any build you hand to testers. If `flutter pub get --enforce-lockfile` fails, the lockfile does not match this SDK: stop and record it, do not regenerate the lock to make it pass.

## 2. Devices and conditions

| Item | Requirement |
| --- | --- |
| Devices | At least one mid-range phone (about 360 × 800 dp) with gesture navigation and one older device or smaller screen with three-button navigation, Android 10 or later |
| Text and display size | Default, then largest font size and largest display size, for section H |
| Network | Wi-Fi; mobile data; Airplane mode toggled mid-request; a throttled network if available |
| Accounts | Same labels and states as the iPhone checklist. Accounts are provided out of band; never write emails, passwords, codes, tokens or playback URLs here |

## 3. Record header (fill once per run)

| Field | Value |
| --- | --- |
| Tester / date (UTC) | |
| Device model, Android version, patch level | |
| Build commit (full SHA), Flutter version, build mode | |
| Gateway URL as built | |
| Account labels used | |

## 4. Android-specific checks

| ID | What to do | Expected | Result | Evidence ref | UTC |
| --- | --- | --- | --- | --- | --- |
| AND-1 | Install the release build, open it, grant nothing | App starts to the Welcome flow; no crash; no debug banner | | | |
| AND-2 **SEC** | Sign in, force-stop the app (Settings → Apps → KoloVibe → Force stop), reopen | Home opens and Profile shows the same account without signing in again (SEC-05) | | | |
| AND-3 **SEC** | Sign in, then clear app data, reopen | Signed out; no previous account visible; the device does not retain the refresh credential (credentials live in the platform secure store) | | | |
| AND-4 **SEC** | Install over the previous build (update, not uninstall), reopen | Behaviour as AND-2; no crash from stored data of the earlier build | | | |
| AND-5 | Open the recent-apps view while signed in | No sensitive screen content is exposed in the task switcher beyond what the product intends | | | |
| AND-6 | Press the system Back button/gesture on every first-level screen, in a form with unsaved text (M-105), during an upload (M-046), and on the sign-in screen | Back never exits unexpectedly with unsaved work; the unsaved-changes dialog appears where designed; Back during upload does not silently cancel it | | | |
| AND-7 | Rotate the device on sign-in, the player (M-024) and the upload screens | Layout stays usable; playback position and form text are not lost, or the app stays portrait by design | | | |
| AND-8 | Pick a real MP4 under 50 MB from Photos/Files (M-042) | The system picker opens; the file is accepted; permission prompts follow M-104 wording; denying permission shows M-104, not a crash | | | |
| AND-9 | Start an upload, lock the screen for 2 minutes, unlock | Upload resumes or fails with M-047/M-048 and can be retried; no duplicate video is created | | | |
| AND-10 | Put the phone in Airplane mode during upload, then restore | M-047 interrupted, retry succeeds with the same reservation | | | |
| AND-11 | Play a published video (M-024) on Wi-Fi and on mobile data; background the app during playback and return | Video decodes with sound; backgrounding pauses; returning does not replay from an expired link without refreshing it | | | |
| AND-12 | Share a video (M-030) | The Android share sheet opens with the public link only | | | |
| AND-13 | Open the device language, font scale and dark mode settings changes while the app runs | No overflow; text remains readable; no layout exception | | | |
| AND-14 | Notification preference screen (M-086) | The app reflects the OS notification permission truthfully and never claims push is enabled when it is not | | | |

## 5. Shared rows

Run rows **A1–H6** of [iphone_e2e_checklist.md](iphone_e2e_checklist.md) on the Android device and record each Result in the table below (copy the row id, expected outcome and endpoint from that file). Interpret "force-close" as AND-2, "Link Conditioner" as the throttled network above, and "home indicator" as the gesture bar.

| Row | Result | Evidence ref | UTC | Defect id |
| --- | --- | --- | --- | --- |
| A1–A12 | | | | |
| B1–B9 | | | | |
| C1–C5 | | | | |
| D1–D6 | | | | |
| E1–E7 | | | | |
| F1–F10 | | | | |
| G1–G7 | | | | |
| H1–H6 | | | | |

## 6. Sign-off

A phone PASS is recorded only when every row above is `PASS` or an explained `N/T` approved by the owner, every **SEC** row is `PASS`, and the record header is complete. Anything else is `FAIL` or `OPEN`. Attach screenshots or screen recordings by reference; do not paste tokens, codes, URLs with signatures or account emails.
