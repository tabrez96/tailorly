---
id: S17
name: Production record
purpose: Owner: see how one garment was made, how long it took, and how that compares with the estimate
size: 390x844
---

## Content and actions
- Header: back button, overline "Production record", title the garment name.
- Hero: Time taken (total logged), with the owner's estimate and the difference in time and percent. In progress: Logged so far, a Running or Paused chip, time left against the estimate and a progress bar (states/in-progress.html).
- Order card: first photo, order number and item position, customer, due date, item status. Tap opens S04.
- Estimate vs time taken (finished items only): three bars, Estimate, Took and the usual time for this product (average of the last 10 finished), plus a one-line pattern for this employee and product.
- Details: made by, when the estimate was set, started, finished, elapsed working days and number of sessions, due date with On time or Late.
- Work sessions: each Start to Pause or Finish from S08, with date, times and length, and the total logged. Pauses and time on other items are not counted.
- Note (finished items): optional free text, "Why it took longer", kept with the record for later review.
- Rework: a rework job has its own record (title "Rework · Blouse", reason chip, estimate vs time taken, sessions). An item that had rework shows a Rework after delivery row under Details with each rework's time, linking to its record.
- Reached from: the Production row on each item card in S04, the Day view list and the Estimate vs time taken list in S12.

## States
- Finished (screen.html).
- In progress (states/in-progress.html): no comparison bars or note yet.
- Not started: hero shows the estimate only and "Not started"; Work sessions shows "No time logged yet."
- No estimate (older items made before estimates): hero shows time taken only, and the comparison shows Took and Usual.
- Loading: grey card outlines.
- Dark theme (states/dark.html).

## Notes and open questions
- The estimate is set by the owner when the order is assigned (S05 or the assign sheet in S16), pre-filled with the usual time. It can be changed until the item is started, then it is fixed, so the comparison stays honest. Owner corrections to session times are not in this version.
- The employee does not see this screen or the estimate in this version.
- Analytics on estimates (by employee, by product, over months) live in S12; more can be added from use.

## Change log
- New screen: production record per item, with time taken, estimate, sessions and a note. Requested in review.
- Added rework records and the Rework after delivery row on the item's record. Requested in review.
- Sample names: the owner is Sabreen and the employee is Ali (Ali Khan). Requested in review.
