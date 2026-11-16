---
id: S09
name: My pay
purpose: Employee: see this week's pay so far and past payments
size: 390x844
---

## Content and actions
- This week so far: total, days worked x daily wage, overtime hours x hourly rate x multiplier, pay day.
- This week: each day with start, end, hours, overtime and that day's pay. Days off show "Off, unpaid".
- Payments received: date, method, period, days and overtime, amount paid.

## States
- Main (screen.html).
- No payments yet: "No payments yet. Your first pay day is Sat <date>."
- Loading: grey outlines.
- Dark theme (states/dark.html): same layout and content, dark tokens. Shown when the device is set to dark.

## Notes and open questions
- Read only. If a day looks wrong, the employee asks the owner to fix it in S10.

## Change log
- First version, from the approved brief.
- Primary colour changed from indigo to mulberry, and a dark theme added (states/dark.html); colours now come from theme tokens in ux.md. Requested in review.
- Restyled for a more modern look: Plus Jakarta Sans replaces the system font; large-title header, pill buttons and chips, tonal secondary buttons, softer card shadows, floating icon navigation. Layout, copy and flows unchanged. Requested in review.
- The key card now uses the mulberry hero gradient (see Design system).
