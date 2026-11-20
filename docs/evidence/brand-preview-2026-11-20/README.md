# D-8 brand preview — owner approval requested

[`D-8-brand-preview.png`](D-8-brand-preview.png) puts the approved Figma **red play mark** next to the current launcher icon at the real iOS sizes (180, 120, 87 and 60 px, drawn 1:1 with the iOS corner mask), on dark and light wallpapers, and shows the current native launch screen next to the approved Figma splash (M-001).

| | Current | Recommended |
| --- | --- | --- |
| Launcher icon | Owner-supplied “K” logo on white (`Icon-App-1024x1024@1x.png`, from a 558 × 569 source) | Figma mark, full-bleed `#E02736` with the white play triangle in the Figma proportions |
| Native launch screen | White, with a 1 × 1 `LaunchImage` (effectively blank) | Deep navy `#001539` with the mark, matching M-001 |
| In-app header and splash | Already the Figma red play mark | Unchanged |

**Findings.** The in-app emblem already follows Figma, so today the brand shows two different marks: the app draws the red play mark, the home screen and the OS launch screen show the “K” logo or nothing. The Figma mark stays legible at 60 px; the full-bleed variant avoids the “icon inside an icon” look of the rounded square on white. The rounded square exactly as drawn in Figma is shown only for comparison, because iOS icons must be opaque and square.

**Not done, by design.** No launcher, splash or in-app asset has been replaced. Replacing them before approval would change the store-facing brand.

**On approval** (separate change): regenerate every iOS and Android launcher size from one 1024 px master (`scripts/generate_mobile_brand_assets.swift` or equivalent), set the launch storyboard to deep navy with the mark, update `docs/mobile-ui-implementation.md` and `docs/mobile-asset-manifest.json`, and check legibility and cropping on a physical iPhone and an Android adaptive-icon mask. Reply “approve Figma mark” or “keep current logo” on issue #100.
