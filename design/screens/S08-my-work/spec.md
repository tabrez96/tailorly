---
id: S08
name: My work
purpose: Employee: start the day, time each work item, switch between items
size: 390x844
---

## Content and actions
- Day card: day started time and time so far; End my day.
- Now working on: item, order, customer, due date, the item's first photo (76 px, with photo count; tap opens details), running timer. Pause stops the timer (item stays first in Up next). Finish item ends the item (it moves to Finished today). Measurements and notes opens the item's details (states/item-detail.html).
- Up next: items assigned to the employee, by due date, each with its first photo (52 px; tap opens that item's details) and garment name first. Switch pauses the current item and starts this one in one tap.
- Finished today: items finished today with photo and time spent.
- Bottom navigation (employee): My work S08, My pay S09.

## States
- Main: day started, timing an item (screen.html).
- Day not started: big Start my day button; item buttons disabled (states/not-started.html).
- Item details sheet (states/item-detail.html): large photo first with all the item's photos below it, then measurements and notes. Prices are not shown to the employee.
- Timing a rework (states/rework.html): the Now working on card reads "Rework · Blouse" with the reason chip and the What to do note from S04; the details sheet shows the item's photos and measurements as made. Rework rows in Up next and Finished today carry a Rework chip. Start, pause, switch and finish work the same way.
- Paused: Now working card shows "Paused" with the item's total time and a Resume button.
- Item with no photo: camera placeholder (Lehenga blouse in the mockup).
- Nothing assigned: "Nothing assigned to you right now."
- Day ended: "Day ended at 7:00 pm. See you tomorrow." Items cannot be started until a new day starts.
- Offline: timer keeps counting on the phone; a banner says "Offline. Your time will be saved when you're back online."
- Dark theme (states/dark.html): same layout and content, dark tokens. Shown when the device is set to dark.

## Notes and open questions
- Start, pause, switch, resume and end are each one tap, because the employee does this with busy hands many times a day.
- Ending the day pauses any running item.
- Forgot to end the day: the owner fixes the time in S10.

## Change log
- First version, from the approved brief.
- Primary colour changed from indigo to mulberry, and a dark theme added (states/dark.html); colours now come from theme tokens in ux.md. Requested in review.
- Restyled for a more modern look: Plus Jakarta Sans replaces the system font; large-title header, pill buttons and chips, tonal secondary buttons, softer card shadows, floating icon navigation. Layout, copy and flows unchanged. Requested in review.
- The key card now uses the mulberry hero gradient (see Design system).
- Every item now shows its garment photo (Now working on, Up next, Finished today), so the employee can recognise work at a glance; the details sheet leads with a large photo. Rows lead with the garment name. Requested in review.
- Up next now follows the order planned in S16, with a line saying so. Requested in review.
- Rework jobs logged after delivery appear in the queue with a Rework chip and their note, and are timed like items (states/rework.html). Requested in review.
- Sample names: the owner is Sabreen and the employee is Ali (Ali Khan). Requested in review.
