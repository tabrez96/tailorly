---
id: S12
name: Production
purpose: Owner: who is working on what right now, what is waiting for someone, and assigning it
size: 390x844
---

## Content and actions
- Header (as the Production tab): overline date and time, title Production, Work plan (tonal pill, opens S16). No back button and no report row.
- **Right now**: one card per employee, those working first. Each shows the avatar, name, day start and time in, and a status chip: Working, Paused, Not in yet, or Gone home (with the day end time).
  - Working: the item being timed (52 px photo, garment and order, customer, item number, due date), the live timer for that item in minutes (updates each minute, not announced), when it started, the estimate and time left, and a bar of time used against the estimate. Over the estimate the bar and the time left turn warning ("20m over").
  - Paused: the item that was paused, when, and the time logged against its estimate.
  - Not in yet: the first items in the queue, and Start Ali's day (records the day start for the employee, the same record as Start my day on S08).
  - Up next for Ali: the next 2 items in that person's queue (rank, garment and order, due date, status chip). Items moved by the owner say "moved by you".
  - Ali's queue (tonal): opens S16 at that person's queue.
  - Give Ali work (primary): opens S16 with the assign sheet (S16 states/assign.html) for the waiting order with the earliest due date, with Ali already chosen as the maker. Shown only while orders are waiting. Choosing Next up there puts it at the top of Ali's Up next on S08, so it is the next thing Ali picks up.
  - Tapping the item opens S04 at that item.
- **Waiting for someone**: every order with no one assigned, earliest due first (photo, garment and order, customer, number of items, due date) with an Assign button on each row, opening the S16 assign sheet for that order. When every order is assigned: "Every order has someone making it."
- **This week so far**: one row with garments finished, on time and late now; opens the production report (states/from-reports.html, Back returns here).
- The Production tab in the owner bottom navigation opens this screen. Holding the tab opens S16 with the assign sheet, as before.
- **Production report** (states/from-reports.html, also opened from Production in S18 Settings, the report row on S11, S13, S14 and the Production this week card on S02): Back, overline Reports, the report row with Production selected, then:
  - Period: Day, Week (default), Month, with previous and next buttons.
  - Headline: garments finished, orders delivered, time logged on garments; in Week and Month a bar per day (per week in Month).
  - On time (delivered by the due date, of delivered) and Late now (past due, not Ready).
  - Estimate vs time taken: totals, the difference, how many took longer, the garments furthest from their estimate (each opens S17), and See all.
  - By garment: count finished, average time and average estimate. By employee: garments finished and time logged out of time present.
  - Coming up: orders due in the next 7 days (View opens S03 filtered to them), garments not started that are due this week.
  - Day view (states/day.html): each finished garment with order, customer, finish time, estimate and time logged (tap opens S17), the day start, end and overtime.

## States
- Main: Ali working on a kurta, 2 orders waiting (screen.html).
- Ali paused, 1 order waiting (states/paused.html).
- Morning, Ali not in yet, nothing waiting (states/not-in-yet.html).
- Gone home: the card shows "Gone home 6:10 pm" with the day's time logged and the first item for tomorrow; no timer.
- No employees yet: "Add someone in Staff to start giving out work." with Add employee (opens S10).
- Loading: grey card outlines. Offline: the last known status with "Updated 11:32 am" under the name.
- Production report: week (states/from-reports.html), day (states/day.html), nothing finished in the period (states/empty.html).
- Dark theme (states/dark.html).

## Notes and open questions
- A garment counts on the day it is finished (Finish item on S08). Ready-made items are not production and are left out.
- Average time per garment uses logged time only, so it is only as good as the employee's timing.
- The tab is for the live shop floor: what each person is doing now and what still needs someone. Finished counts and late work are a report, so they live in Reports, one row away.
- The live status comes from the employee's own timing on S08; if they forget to start a timer the card says "Not timing anything" (warning chip) rather than guessing.

## Change log
- First version: production per day, week and month. Requested in review.
- Added Estimate vs time taken; garments in the Day view and the estimate list open S17; average estimate per garment. Requested in review.
- Sample names: the owner is Sabreen and the employee is Ali (Ali Khan). Requested in review.
- Reports moved into S18 Settings: back button added; also opened from Report on S16. Requested in review.
- Owner navigation reordered to Today, Orders, Customers, Products, Production; the Production tab now opens S12, and holding it opens S16 with the assign sheet. Requested in review. This screen is now the tab: no back button, Work plan pill and a Not assigned row with Assign; the Reports version moved to states/from-reports.html.
- The Production tab now shows who is working on what right now (live item, timer against the estimate, Up next), orders waiting for someone with Assign on each, and Give Ali work; the finished-work report moved to the Reports version (states/from-reports.html, states/day.html, states/empty.html). New states/paused.html and states/not-in-yet.html. Requested in review.
- Header: the overline date sits above, and the title Production shares its row with the Work plan pill on the right; the title no longer takes a full row. From Reports (states/from-reports.html, states/day.html), Back sits on its own row above the overline. Requested in review.
