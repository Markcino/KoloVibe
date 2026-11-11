# FL-A account/settings/system screen gaps before implementation

Baseline main b1971d9b0a9a07f99d3f18bc1ecfc344fc909c1c. Recipes are domain bundles; M-NNN refers to each bundled screen number. Inspection completed before implementation edits.

| Screen | Recipe | Gap found |
|---|---|---|
| M-001 | Splash Screen | Restore exists at app startup; splash has a separate timed welcome transition and generic restore errors. |
| M-002 | Welcome Screen | Welcome navigation exists; verify live entry routing. |
| M-003 | A world of original voices | Recipe introduction/navigation exists; preserve discovery intent. |
| M-004 | Sign in | Live sign-in exists; typed failures/navigation and cleared secret controllers need verification. |
| M-005 | Create an account | Live registration exists; 409 does not select M-012 and email is not carried to verification. |
| M-006 | Verify your email | Verification endpoint exists; sample email/short sample code must be replaced by live form/context. |
| M-007 | Resend verification | Resend recipe action is unavailable and live navigation bypasses this screen. |
| M-008 | Verification expired | Resend endpoint exists; preserve email and handle real failures. |
| M-009 | Forgot password | Reset request endpoint exists; preserve email and typed failures. |
| M-010 | Reset password | Reset endpoint exists with extra reset-code field; success currently skips M-011. |
| M-011 | Password reset | Static success recipe; route here only after real reset completion. |
| M-012 | Account already exists | Static recipe; not wired to actual registration 409. |
| M-013 | Make it yours | Recipe currently navigates without saving display_name; photo policy unavailable. |
| M-014 | Your voice belongs here | Creator introduction intent already routes setup/explore; verify role-neutral entry. |
| M-015 | Sign-in problem | Retry sign-in recipe exists; generic errors lose actionable failure type. |
| M-016 | Confirm it’s you | do:reauthenticate is not implemented; needs current /me email and typed result to caller. |
| M-079 | My account | Live /me exists; account view omits recipe settings/profile/role-based creator entries and bypasses logout confirmation. |
| M-080 | Edit personal profile | Generic saveProfile exists; current name/email not loaded, photo affordance not honest native outcome. |
| M-081 | Account settings | Generic protected recipe unavailable with live dependencies; settings links need live route. |
| M-082 | Change password | PATCH /me/password exists via generic reset operation; clears current session and skips sessions note. |
| M-083 | Active sessions | Live list/revoke exists; verify recipe, current-session protection and common system failures. |
| M-084 | Privacy settings | Live privacy exists; compare recipe links, add token-based access request handling. |
| M-085 | Security settings | Live email read exists but Email verified is hard-coded; remove unverified assertion. |
| M-086 | Notification preferences | Live preference reads/writes exist; device-settings action is absent and permission-off claim is hard-coded. |
| M-087 | Community guidelines | Static recipe principles exist; keep literal recipe content and safe back navigation. |
| M-088 | Terms & Privacy | Static tabs/summary exist; configured official HTTPS links missing. |
| M-089 | Help & Support | Static help topics exist; support action unavailable and configured links missing. |
| M-090 | Logout confirmation | Generic protected confirmation unavailable; live account page logs out directly. |
| M-091 | Delete account request | Live intake intro exists; currently goes to inline password flow instead of M-016 recipe return. |
| M-092 | Confirm account deletion | Live intake POST uses current_password; missing reauth token, expiry/single-use and duplicate-open handling. |
| M-093 | Deletion request received | Live receipt list exists; hard-codes received and omits actual id/status. |
| M-094 | Privacy request received | Live access receipt exists; hard-codes received and omits actual id/status. |
| M-095 | No Internet Connection | Static offline recipe; no ApiFailure mapping or retry operation. |
| M-096 | Slow Connection | Static slow connection recipe; no request-threshold binding. |
| M-097 | Loading Skeleton | Static skeleton recipe; no reusable request-loading widget. |
| M-098 | No search results | Static search-empty recipe includes sample result/actions; no reusable factual empty widget. |
| M-099 | Application error | Static error recipe; no unexpected failure binding. |
| M-100 | Access denied | Static/protected access-denied recipe; no 403 mapping. |
| M-101 | Session expired | Static expire/sign-in recipe; no shared live refresh-failure state UI. |
| M-102 | Service unavailable | Static unavailable recipe; no 503 mapping. |
| M-103 | Rate limit exceeded | Static rate-limit recipe; no 429 mapping or operation retry. |
| M-104 | Media permission | Static/protected media-permission recipe; needs real openAppSettings action. |
| M-105 | Unsaved Changes Warning | Inline generic form discard prompt exists; no public reusable PopScope guard. |
| M-106 | Destructive-Action Confirmation | Static destructive example targets deleteVideo; needs generic reusable confirmation dialog. |
| M-107 | Success Notification | Static success example; no reusable notification API tied to real completed actions. |
| M-108 | Application Update / Compatibility Notice | Static update recipe; no startup compatibility read/version/device-store binding. |
