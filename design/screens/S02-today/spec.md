---
id: S02
name: Today
purpose: Owner's home: who is working, what is due, money to collect
size: 390x844
---

## Content and actions
- Header: overline date, title Today, and a round Settings (gear) button on the right that opens S18.
- Staff card: employee's day status (started at, time so far), the item they are timing now, End day button (records end of day for them, same as S10).
- Due in the next 2 days: orders due today and tomorrow and the day after, with status chip. Tap opens S04.
- Money: total to collect across open invoices (tap opens S03 filtered to orders with a balance) and payments received this week.
- Staff pay: this week's pay so far for the employee. Tap opens S10.
- Shortcuts: press and hold a nav tab (see below). The first time the owner signs in after this change, a tip explains it (states/hold-tip.html, shown once, Got it closes it).
- Bottom navigation (owner): Today S02, Orders S03, Customers S06, Products S15, Production S12. A short tap opens the tab. Press and hold a tab (500 ms) to open its create page: Orders opens S05 New order; Customers opens the add customer form on S06; Products opens an empty product sheet on S15; Production opens S16 Work plan with the assign sheet (states/assign.html) for the waiting order with the earliest due date. Today has no hold action. Each tab also keeps a visible button in its header (+ New order on S03, + Add on S06 and S15, Assign on S12 and S16), so holding is never the only way.
- Production this week card: garments finished, how many took longer than estimated, and a Late chip; opens the S12 production report (S12 states/from-reports.html).

## States
- Main: working day (screen.html).
- First run: no employee, customer or order yet; a three-step setup list (states/first-run.html).
- Employee has not started the day: staff card shows "Not started yet" with a Start day button.
- Nothing due: "Nothing due in the next 2 days." in place of the list.
- Loading: card outlines in grey, no numbers.
- Hold tip (states/hold-tip.html): page dimmed, the Orders tab ringed in saffron, a card above the nav listing what holding each tab does, and Got it.
- Dark theme (states/dark.html): same layout and content, dark tokens. Shown when the device is set to dark.

## Notes and open questions
- Phone first: the owner checks this between customers, so it answers "who is working, what is due, who owes me" without scrolling far.

## Change log
- First version, from the approved brief.
- Primary colour changed from indigo to mulberry, and a dark theme added (states/dark.html); colours now come from theme tokens in ux.md. Requested in review.
- Restyled for a more modern look: Plus Jakarta Sans replaces the system font; large-title header, pill buttons and chips, tonal secondary buttons, softer card shadows, floating icon navigation. Layout, copy and flows unchanged. Requested in review.
- The key card now uses the mulberry hero gradient (see Design system).
- New order moved from the floating saffron pill to a 56 px round saffron plus button raised in a notch of the bottom navigation, between Orders and Customers. Requested in review.
- Added a Work plan card under Ali's day: orders still to assign and the suggested next item; opens S16. New order button moved out of the nav bar to a round button beside it. Requested in review.
- Added a Production this week card under Work plan, so the report is one tap from Today. Requested in review.
- The plus button now opens a New sheet with Sale order (S05) and Production (S16, or Assign on a waiting order), so starting production is as quick as starting a sale. Accessible name changed to "New sale or production". Requested in review.
- Added the Settings (gear) button to the header, opening S18 Settings. Requested in review (MCP settings).
- Sample names: the owner is Sabreen and the employee is Ali (Ali Khan). Requested in review. The S02 overline greets Sabreen.
- Owner navigation is now Today, Orders, Production, Customers, Products; the round plus button and the New sheet are gone; Staff and Reports moved into S18 Settings. Requested in review. The New sheet state (states/new-menu.html) is replaced by states/hold-tip.html. Staff pay card still opens S10.
- Owner navigation reordered to Today, Orders, Customers, Products, Production; the Production tab now opens S12, and holding it opens S16 with the assign sheet. Requested in review.
- Production this week card now opens the production report, since the Production tab shows live work. Requested in review.
