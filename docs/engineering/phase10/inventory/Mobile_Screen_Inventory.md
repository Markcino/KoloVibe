# Mobile screen inventory (generated)

Sources: `docs/mobile-design-coverage.md` (designed screens M-001 to M-108, with live-wiring status) and `apps/mobile/lib/features/business/business_screens.dart` (Business screens M-109 to M-144). **108 designed + 36 Business = 144 screens**; 106 Dart source files; 57 test files. There are **no** screens for events, ticketing, advertising or financial accounts (no approved design and no backend).

'Binding mode' and 'Endpoint' are copied from the coverage register's binding tables (latest wins); 'Visual class' from its 20 November review. They are a record, not a fresh assessment. A screen is accepted only through its tests and, later, device UAT; none has been run on a device.

## Designed screens (M-001 to M-108)

| Route | Screen | Design group | PRD | Binding mode | Endpoint / condition | Visual class (20 Nov) |
| --- | --- | --- | --- | --- | --- | --- |
| M-001 | Splash Screen | account | PRD-F01, PRD-F09 | Live | POST /auth/refresh; GET /me | Not verified |
| M-002 | Welcome Screen | account | PRD-F01, PRD-F09 | Static | — | Not verified |
| M-003 | A world of original voices | account | PRD-F01, PRD-F09 | Static | — | Not verified |
| M-004 | Sign in | account | PRD-F01, PRD-F09 | Live | POST /auth/login | Visually matched |
| M-005 | Create an account | account | PRD-F01, PRD-F09 | Live | POST /auth/register | Visually matched |
| M-006 | Verify your email | account | PRD-F01, PRD-F09 | Live | POST /auth/verify | Functional, visually different |
| M-007 | Resend verification | account | PRD-F01, PRD-F09 | Live | POST /auth/verification/resend | Functional, visually different |
| M-008 | Verification expired | account | PRD-F01, PRD-F09 | Live | POST /auth/verification/resend | Functional, visually different |
| M-009 | Forgot password | account | PRD-F01, PRD-F09 | Live | POST /auth/password/reset-request | Functional, visually different |
| M-010 | Reset password | account | PRD-F01, PRD-F09 | Live | POST /auth/password/reset | Functional, visually different |
| M-011 | Password reset | account | PRD-F01, PRD-F09 | Live result | — | Functional, visually different |
| M-012 | Account already exists | account | PRD-F01, PRD-F09 | Live result | — | Functional, visually different |
| M-013 | Make it yours | account | PRD-F01, PRD-F09 | Live | GET /me; PATCH /me | Functional, visually different |
| M-014 | Your voice belongs here | account | PRD-F01, PRD-F09 | Static | — | Functional, visually different |
| M-015 | Sign-in problem | account | PRD-F01, PRD-F09 | Live | POST /auth/login | Functional, visually different |
| M-016 | Confirm it’s you | account | PRD-F01, PRD-F09 | Live | GET /me; POST /me/reauthenticate | Functional, visually different |
| M-017 | Multi-Service Home Dashboard | discovery | PRD-F04, PRD-F05 | not in these tables (see FL-D and Phase 4 matrices) |  | Visually matched |
| M-018 | Following Video Feed | discovery | PRD-F04, PRD-F05 | not in these tables (see FL-D and Phase 4 matrices) |  | Functional, visually different |
| M-019 | Explore & Discover | discovery | PRD-F04, PRD-F05 | not in these tables (see FL-D and Phase 4 matrices) |  | Functional, visually different |
| M-020 | Trending originals | discovery | PRD-F04, PRD-F05 | not in these tables (see FL-D and Phase 4 matrices) |  | Functional, visually different |
| M-021 | Search | discovery | PRD-F04, PRD-F05 | not in these tables (see FL-D and Phase 4 matrices) |  | Functional, visually different |
| M-022 | Search results | discovery | PRD-F04, PRD-F05 | not in these tables (see FL-D and Phase 4 matrices) |  | Functional, visually different |
| M-023 | Search filters | discovery | PRD-F04, PRD-F05 | not in these tables (see FL-D and Phase 4 matrices) |  | Functional, visually different |
| M-024 | Full-Screen Vertical Video Feed / Player | discovery | PRD-F04, PRD-F05 | not in these tables (see FL-D and Phase 4 matrices) |  | Functional, visually different |
| M-025 | Video Details | discovery | PRD-F04, PRD-F05 | not in these tables (see FL-D and Phase 4 matrices) |  | Functional, visually different |
| M-026 | Ama Kollie | discovery | PRD-F04, PRD-F05 | not in these tables (see FL-D and Phase 4 matrices) |  | Functional, visually different |
| M-027 | Ama’s published videos | discovery | PRD-F04, PRD-F05 | not in these tables (see FL-D and Phase 4 matrices) |  | Functional, visually different |
| M-028 | Follow / Unfollow State | discovery | PRD-F04, PRD-F05 | not in these tables (see FL-D and Phase 4 matrices) |  | Not verified |
| M-029 | Like / Unlike State | discovery | PRD-F04, PRD-F05 | not in these tables (see FL-D and Phase 4 matrices) |  | Not verified |
| M-030 | Native Share State | discovery | PRD-F04, PRD-F05 | not in these tables (see FL-D and Phase 4 matrices) |  | Not verified |
| M-031 | Video unavailable | discovery | PRD-F04, PRD-F05 | not in these tables (see FL-D and Phase 4 matrices) |  | Not verified |
| M-032 | Video Buffering | discovery | PRD-F04, PRD-F05 | not in these tables (see FL-D and Phase 4 matrices) |  | Not verified |
| M-033 | Video Playback Error | discovery | PRD-F04, PRD-F05 | not in these tables (see FL-D and Phase 4 matrices) |  | Not verified |
| M-034 | Low-Bandwidth Playback | discovery | PRD-F04, PRD-F05 | not in these tables (see FL-D and Phase 4 matrices) |  | Not verified |
| M-035 | Restricted video | discovery | PRD-F04, PRD-F05 | not in these tables (see FL-D and Phase 4 matrices) |  | Not verified |
| M-036 | Become a creator | discovery | PRD-F04, PRD-F05 | Live | GET /creators/me/upload-eligibility; GET/POST /creators/me/application | Functional, visually different |
| M-037 | Creator Studio | studio | PRD-F03, PRD-F04 | Live (partial) | Same, plus GET /creators/me | Functional, visually different |
| M-038 | Creator profile | studio | PRD-F03, PRD-F04 | Live | GET /creators/me; GET /creators/{id} (count only) | Functional, visually different |
| M-039 | Edit creator profile | studio | PRD-F03, PRD-F04 | Live | PATCH /creators/me | Functional, visually different |
| M-040 | My video library | studio | PRD-F03, PRD-F04 | not in these tables (see FL-D and Phase 4 matrices) |  | Functional, visually different |
| M-041 | Create an original | studio | PRD-F03, PRD-F04 | Live | GET /creators/me/upload-eligibility | Functional, visually different |
| M-042 | Select a video | studio | PRD-F03, PRD-F04 | Live (inside M-041 flow) | Platform picker | Functional, visually different |
| M-043 | Check your file | studio | PRD-F03, PRD-F04 | Live (inside M-041 flow) | Local checks; server validates media | Functional, visually different |
| M-044 | Tell the story | studio | PRD-F03, PRD-F04 | Live (inside M-041 flow) | POST /videos | Functional, visually different |
| M-045 | Choose a cover | studio | PRD-F03, PRD-F04 | Not wired | — | Not verified |
| M-046 | Uploading your original | studio | PRD-F03, PRD-F04 | Live (inside M-041 flow) | POST /videos/{id}/upload-intents; PUT signed URL; POST /videos/{id}/upload-status | Not verified |
| M-047 | Upload interrupted | studio | PRD-F03, PRD-F04 | Live (inside M-041 flow) | Same, resumed at the failed step | Not verified |
| M-048 | Upload failed | studio | PRD-F03, PRD-F04 | Live (inside M-041 flow) | GET/POST /videos/{id}/upload-status | Not verified |
| M-049 | Preparing your video | studio | PRD-F03, PRD-F04 | Live (inside M-041 flow) | GET /videos/{id}/upload-status | Not verified |
| M-050 | Pending moderation | studio | PRD-F03, PRD-F04 | not in these tables (see FL-D and Phase 4 matrices) |  | Not verified |
| M-051 | Your original is published | studio | PRD-F03, PRD-F04 | not in these tables (see FL-D and Phase 4 matrices) |  | Not verified |
| M-052 | Video rejected | studio | PRD-F03, PRD-F04 | not in these tables (see FL-D and Phase 4 matrices) |  | Not verified |
| M-053 | Manage video | studio | PRD-F03, PRD-F04 | not in these tables (see FL-D and Phase 4 matrices) |  | Functional, visually different |
| M-054 | Edit video details | studio | PRD-F03, PRD-F04 | not in these tables (see FL-D and Phase 4 matrices) |  | Not verified |
| M-055 | Unpublish confirmation | studio | PRD-F03, PRD-F04 | not in these tables (see FL-D and Phase 4 matrices) |  | Not verified |
| M-056 | Delete video confirmation | studio | PRD-F03, PRD-F04 | not in these tables (see FL-D and Phase 4 matrices) |  | Not verified |
| M-057 | Content status notice | studio | PRD-F03, PRD-F04 | not in these tables (see FL-D and Phase 4 matrices) |  | Not verified |
| M-058 | Creator analytics | studio | PRD-F03, PRD-F04 | not in these tables (see FL-D and Phase 4 matrices) |  | Not verified |
| M-059 | Video analytics | studio | PRD-F03, PRD-F04 | not in these tables (see FL-D and Phase 4 matrices) |  | Not verified |
| M-060 | Creator Analytics — Empty / Unavailable | studio | PRD-F03, PRD-F04 | not in these tables (see FL-D and Phase 4 matrices) |  | Not verified |
| M-061 | Lone Stars | points | PRD-F06, PRD-F07 | not in these tables (see FL-D and Phase 4 matrices) |  | Functional, visually different |
| M-062 | Confirmed Lone Stars | points | PRD-F06, PRD-F07 | not in these tables (see FL-D and Phase 4 matrices) |  | Functional, visually different |
| M-063 | Pending Lone Stars | points | PRD-F06, PRD-F07 | not in these tables (see FL-D and Phase 4 matrices) |  | Functional, visually different |
| M-064 | Transaction history | points | PRD-F06, PRD-F07 | not in these tables (see FL-D and Phase 4 matrices) |  | Functional, visually different |
| M-065 | Transaction details | points | PRD-F06, PRD-F07 | not in these tables (see FL-D and Phase 4 matrices) |  | Functional, visually different |
| M-066 | Withheld points | points | PRD-F06, PRD-F07 | not in these tables (see FL-D and Phase 4 matrices) |  | Functional, visually different |
| M-067 | Reversed points | points | PRD-F06, PRD-F07 | not in these tables (see FL-D and Phase 4 matrices) |  | Functional, visually different |
| M-068 | Engagement eligibility | points | PRD-F06, PRD-F07 | not in these tables (see FL-D and Phase 4 matrices) |  | Functional, visually different |
| M-069 | No points activity | points | PRD-F06, PRD-F07 | not in these tables (see FL-D and Phase 4 matrices) |  | Functional, visually different |
| M-070 | Report Video Entry | moderation | PRD-F08 | not in these tables (see FL-D and Phase 4 matrices) |  | Not verified |
| M-071 | Report a video | moderation | PRD-F08 | not in these tables (see FL-D and Phase 4 matrices) |  | Functional, visually different |
| M-072 | Report details | moderation | PRD-F08 | not in these tables (see FL-D and Phase 4 matrices) |  | Functional, visually different |
| M-073 | Report submitted | moderation | PRD-F08 | not in these tables (see FL-D and Phase 4 matrices) |  | Functional, visually different |
| M-074 | Report submission error | moderation | PRD-F08 | not in these tables (see FL-D and Phase 4 matrices) |  | Functional, visually different |
| M-075 | Already reported | moderation | PRD-F08 | not in these tables (see FL-D and Phase 4 matrices) |  | Functional, visually different |
| M-076 | Content restriction notice | moderation | PRD-F08 | not in these tables (see FL-D and Phase 4 matrices) |  | Functional, visually different |
| M-077 | Account status | moderation | PRD-F08 | not in these tables (see FL-D and Phase 4 matrices) |  | Functional, visually different |
| M-078 | Appeal / Review Request | moderation | PRD-F08 | not in these tables (see FL-D and Phase 4 matrices) |  | Functional, visually different |
| M-079 | My account | settings | PRD-F01, PRD-F09 | Live | GET /me | Functional, visually different |
| M-080 | Edit personal profile | settings | PRD-F01, PRD-F09 | Live | GET /me; PATCH /me | Functional, visually different |
| M-081 | Account settings | settings | PRD-F01, PRD-F09 | Live/static | GET /me | Functional, visually different |
| M-082 | Change password | settings | PRD-F01, PRD-F09 | Live | PATCH /me/password | Functional, visually different |
| M-083 | Active sessions | settings | PRD-F01, PRD-F09 | Live | GET /me/sessions; DELETE /me/sessions/{id} | Functional, visually different |
| M-084 | Privacy settings | settings | PRD-F01, PRD-F09 | Live/static | POST /me/reauthenticate; POST /me/privacy-requests | Functional, visually different |
| M-085 | Security settings | settings | PRD-F01, PRD-F09 | Live | GET /me | Functional, visually different |
| M-086 | Notification preferences | settings | PRD-F01, PRD-F09 | Live/native | GET/PATCH /me/preferences | Not verified |
| M-087 | Community guidelines | settings | PRD-F01, PRD-F09 | Static/native | — | Functional, visually different |
| M-088 | Terms & Privacy | settings | PRD-F01, PRD-F09 | Static/native | — | Functional, visually different |
| M-089 | Help & Support | settings | PRD-F01, PRD-F09 | Static/native | — | Functional, visually different |
| M-090 | Logout confirmation | settings | PRD-F01, PRD-F09 | Live | GET /me; POST /auth/logout | Functional, visually different |
| M-091 | Delete account request | settings | PRD-F01, PRD-F09 | Live | GET /me; POST /me/reauthenticate via M-016 | Functional, visually different |
| M-092 | Confirm account deletion | settings | PRD-F01, PRD-F09 | Live | POST /me/privacy-requests | Functional, visually different |
| M-093 | Deletion request received | settings | PRD-F01, PRD-F09 | Live | GET /me/privacy-requests or POST receipt | Not verified |
| M-094 | Privacy request received | settings | PRD-F01, PRD-F09 | Live | GET /me/privacy-requests or POST receipt | Not verified |
| M-095 | No Internet Connection | states | PRD-F01, PRD-F04, PRD-F09 | Live/reusable | — | Functional, visually different |
| M-096 | Slow Connection | states | PRD-F01, PRD-F04, PRD-F09 | Live/reusable | — | Not verified |
| M-097 | Loading Skeleton | states | PRD-F01, PRD-F04, PRD-F09 | Reusable | — | Not verified |
| M-098 | No search results | states | PRD-F01, PRD-F04, PRD-F09 | Reusable | — | Functional, visually different |
| M-099 | Application error | states | PRD-F01, PRD-F04, PRD-F09 | Live/reusable | — | Functional, visually different |
| M-100 | Access denied | states | PRD-F01, PRD-F04, PRD-F09 | Live/reusable | — | Functional, visually different |
| M-101 | Session expired | states | PRD-F01, PRD-F04, PRD-F09 | Live/reusable | POST /auth/refresh | Functional, visually different |
| M-102 | Service unavailable | states | PRD-F01, PRD-F04, PRD-F09 | Live/reusable | — | Functional, visually different |
| M-103 | Rate limit exceeded | states | PRD-F01, PRD-F04, PRD-F09 | Live/reusable | — | Functional, visually different |
| M-104 | Media permission | states | PRD-F01, PRD-F04, PRD-F09 | Native/reusable | — | Functional, visually different |
| M-105 | Unsaved Changes Warning | states | PRD-F01, PRD-F04, PRD-F09 | Native/reusable | — | Not verified |
| M-106 | Destructive-Action Confirmation | states | PRD-F01, PRD-F04, PRD-F09 | Native/reusable | — | Not verified |
| M-107 | Success Notification | states | PRD-F01, PRD-F04, PRD-F09 | Native/reusable | — | Not verified |
| M-108 | Application Update / Compatibility Notice | states | PRD-F01, PRD-F04, PRD-F09 | Live/native | GET /app/compatibility?platform=&version= | Not verified |

## Business screens (M-109 to M-144, native, no Figma recipe)

| Route | Screen |
| --- | --- |
| M-109 | Home |
| M-110 | Categories |
| M-111 | Results |
| M-112 | Filters |
| M-113 | Detail |
| M-114 | Hours |
| M-115 | Contact |
| M-116 | Reviews |
| M-117 | Privacy |
| M-118 | Ask |
| M-119 | My inquiries |
| M-120 | Conversation |
| M-121 | Write review |
| M-122 | My reviews |
| M-123 | Edit review |
| M-124 | Withdraw review |
| M-125 | Report |
| M-126 | My businesses |
| M-127 | Register |
| M-128 | Manage |
| M-129 | Edit profile |
| M-130 | Edit contacts |
| M-131 | Edit hours |
| M-132 | Profile status |
| M-133 | Verification |
| M-134 | Listing |
| M-135 | Inbox |
| M-136 | Inbox thread |
| M-137 | Owner reviews |
| M-138 | Review invitations |
| M-139 | Team |
| M-140 | Redeem |
| M-141 | Switcher |
| M-142 | Access removed |
| M-143 | Leave |
| M-144 | Staff home |
