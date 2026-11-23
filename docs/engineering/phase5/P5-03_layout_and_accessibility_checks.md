# P5-03 — Layout and accessibility checks

**Type:** regression guard (test only; no production change). **Scope items:** responsive layout checks, accessible keyboard navigation, clear error messages.

`apps/web_django/tests/test_layout_accessibility.py` (11 tests) renders real console pages (sign-in, MFA, the video and report queues with data, an unavailable queue and the account page) and checks the HTML the server sends, then checks the stylesheet.

**Rendered pages**
- `lang="en"`, a responsive viewport that does not disable zoom, no duplicate ids;
- one `main` landmark with `id="main"` and `tabindex="-1"` and a skip link that targets it, at most one `h1`;
- every image has alt text; every button and link has an accessible name (an image's alt text counts, as for the brand link);
- every table has a caption and `scope` on every header; every data cell has a `data-label` so rows reflow into cards on narrow screens;
- every scrolling table region is keyboard reachable (`tabindex="0"`) and named (`role="region"`, `aria-label`);
- every form control has a visible label or accessible name; every POST form carries a CSRF token;
- an unavailable page shows a heading, not only a colour.

**Stylesheet**
- layout rules at four breakpoints (600, 840 and the max-width pairs) and wide tables scroll inside their own region, not the page;
- focus is never removed without a replacement indicator (the global `:focus-visible` outline, and a border plus inset shadow where inputs replace it);
- links and buttons in tables, text buttons and pagination meet the 48 px target;
- reduced motion, more contrast, forced colours and dark scheme are all honoured.

Mutation checks: removing a cell label, the scroll region's name and focusability, a header scope, and shrinking a touch target each fail the matching tests (seven failures); reverted. Whole web suite OK.

## What this is not
These are static checks of delivered HTML and CSS. **No screen-reader pass, browser check at real widths or keyboard walk-through on a device was performed**; do those before calling the console accessibility-accepted. The sample covers the pages listed; the fraud review page (#214) and others can be added to the sample list.
