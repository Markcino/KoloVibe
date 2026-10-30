# KoloVibe Documentation

This directory contains KoloVibe's product requirements, architecture specifications, security reviews, delivery plans and historical decision records.

## Sections

| Section | Contents |
| --- | --- |
| [Requirements](requirements/) | Approved scope PRD/SRS, role permissions, engagement rules and sign-off documents |
| [Architecture](architecture/) | Architecture drawings, OpenAPI draft, database model, risk register, decision log and security control matrix |
| [Engineering](engineering/) | Technical delivery plan, implementation tracker and open engineering decisions |
| [Planning](planning/) | Project roadmap and development trackers |
| [History](history/) | Earlier architecture reviews and change records |

Current delivery status: [Stage 3 execution status](engineering/Stage3_Current_Status.md), [implementation tracker](engineering/Stage3_Implementation_Tracker.csv), and [FND-01 solo-developer governance](engineering/FND-01_repository_governance.md).

Additional team guidance: [engineering standards](engineering-standards.md), [architecture decision overview](architecture-decisions.md), [approved mobile design](mobile-design.md), [mobile UI implementation](mobile-ui-implementation.md), [108-state coverage](mobile-design-coverage.md), and [local asset manifest](mobile-asset-manifest.json).

## Document status

Files retain their source naming and document control labels. **DRAFT**, **proposed**, **pending approval** and **scope approved** are distinct states. Copying a file into Git does not constitute architecture sign-off, completion of a security test, or authorization to deploy.

The approved mobile design is stored in [Figma](https://www.figma.com/design/ANaV0jnwjZ0LEcByTc98HP/KoloVibe?node-id=0-1); Git contains the design reference, not a re-created Figma binary.

## Source fidelity and provenance

The project archive includes documentation brought from the project file library. The following conventions apply:

- `.md`, `.yaml`, `.sql`, `.mmd` and `.csv` files were imported as retrieved text.
- Word `.docx` documents are stored as **readable `.md` text editions** with a source-file notice. Their original Word layout, page styling and embedded images are not included.
- Excel `.xlsx` trackers are also stored as **text editions**; original workbook formatting, formulas, validation and spreadsheet interaction are not preserved.
- Versioned architecture text editions were removed; current unversioned registers, diagrams and contract files remain the working references.
- Duplicate consolidated decision exports and ZIP bundles are intentionally not added to avoid multiple copies of the same materials.
- Other unrelated personal and company documents are excluded.

When exact office-format source files or workbook formulas are necessary, obtain them from the original controlled files, not these text editions.

## Maintenance

Update the appropriate document when a material architecture, scope or security decision changes. Record review and approval status; do not silently convert open issues into settled choices. Avoid committing passwords, private keys, live account data or sensitive identity material.
