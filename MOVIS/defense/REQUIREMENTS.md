# Requirements and source interpretation

Primary source: the user's CAPSTONEmovis.docx at
C:\Users\ASUS\OneDrive\Desktop\CAPSTONEmovis.docx, read on 2026-10-03.
The file was preserved. Paragraph text was extracted from its Word XML for review.
The source's IPO shapes repeat some text; these repetitions do not add requirements.

## Actual project content

Chapter 1's project narrative, IPO conceptual framework, objectives, problem
statement and Scope, Limitations and Delimitation describe MOVIS:

| Source section | Requirement | Implementation evidence |
|---|---|---|
| IPO inputs | User account/role, item quantity/location, smartphone photograph, returned-item details | users, stock, locations, scans, returns tables |
| IPO process | Trained YOLO detects multiple visible items, user verifies quantities | Android still-photo review; optional YOLO adapter; demo explicitly labeled |
| IPO process | Compare verified count with stored stock and preserve previous/verified/difference/time/user | Android Complete count; /adjustments; adjustments and movements |
| Specific objectives 1–3 | Visual scanner, authorized verified stock changes, return statuses | Android Photo, Edit quantity and Returns |
| IPO outputs | Inventory, scan, adjustment and return histories/reports | /reports/*, Android Reports, web inventory/activity/returns |
| Specific objective 4 and problem statement | Evaluate functionality, usability, performance | EVALUATION.md; results remain uncollected |
| Limitations | Lighting, distance, arrangement, overlap, hidden objects and training coverage affect accuracy | Manual verification; no reliable hidden-item counting claim |
| Delimitations | One selected warehouse, smartphone captured images; exclude continuous surveillance, drones, robotics and automatic approval | Still-photo Android workflow and explicit confirmation |

The document supplies no concrete warehouse name, final item classes, labeled
dataset, tested model, actual participant count, measured results or hardware
benchmarks. These cannot be invented.

## User additions and implementation choices

The user requested Android plus a separate inventory website, GitHub/Render/Neon
deployment independent of a personal computer, incoming-stock addition with an
option to discard, manual corrections and website security changes. Incoming
addition is distinct from the document's count reconciliation; both are supported.
Administrator/operator/viewer roles, 12–128 character new passwords, eight-hour
absolute sessions, 30-minute API idle expiry, 15-minute browser interaction lock,
HTTP cookies, rate-limit settings and CPU inference hosting are design choices,
not requirements explicitly stated in the source document.

## Template content not treated as project requirements

Later sections contain generic instructions for writing RRL, technical feasibility,
diagrams, results/discussion, conclusions and reference formatting. Examples about
other products, hardware, technology stacks and books illustrate writing formats;
they do not establish MOVIS functionality or evaluated findings. The document also
uses Chapter 3 for both methodology and results/discussion. Confirm the required
chapter numbering with the adviser before final submission.

Sample bibliography entries and introductory research claims have not been
validated as a MOVIS literature review in this software audit. Replace template
material with the project's actual method and verified research references. Report
only measured outcomes, and keep literature claims separate from software tests.
