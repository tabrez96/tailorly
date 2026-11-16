---
id: S10
name: Staff
purpose: Owner: attendance, overtime and weekly pay for each employee
size: 390x844
---

## Content and actions
- Header: Back (to S18), title Staff, + Add. Reached from Staff in S18 Settings and the Staff pay card on S02. A sub-page with no bottom navigation.
- Employee card: name, daily wage, hourly rate, overtime multiplier; Edit opens states/edit-employee.html. + Add opens the same form empty.
- Week picker (Mon to Sun).
- Day rows: start, end, overtime, day pay. Tap a day to add or fix its start and end time. End day for a day in progress; Add for a missing day.
- This week: days x wage, overtime, total to pay. Record payout opens states/record-payout.html.
- Past payouts: date, method, period, amount.

## States
- Main (screen.html).
- Record payout sheet (states/record-payout.html): amount defaults to the calculated total and can be changed; date and method.
- Edit employee (states/edit-employee.html): name, phone (login), daily wage, overtime multiplier, reset password.
- No employees: "Add your employee to track their days and pay." with + Add.
- Week already paid: total card shows "Paid Sat 14 Nov, Cash, 3,400" instead of Record payout.
- Dark theme (states/dark.html): same layout and content, dark tokens. Shown when the device is set to dark.

## Notes and open questions
- Overtime = time past 8 hours in a day, from day start and end, counted to the minute; pay rounded to the rupee.
- A day with no start and end is unpaid. Week runs Monday to Sunday; pay day defaults to Saturday.
- With one employee the screen shows them directly; with more, the employee card becomes a picker.
- Open: advances against pay and public holidays are not handled.

## Change log
- First version, from the approved brief.
- Primary colour changed from indigo to mulberry, and a dark theme added (states/dark.html); colours now come from theme tokens in ux.md. Requested in review.
- Restyled for a more modern look: Plus Jakarta Sans replaces the system font; large-title header, pill buttons and chips, tonal secondary buttons, softer card shadows, floating icon navigation. Layout, copy and flows unchanged. Requested in review.
- New order moved from the floating saffron pill to a 56 px round saffron plus button raised in a notch of the bottom navigation, between Orders and Customers. Requested in review.
- New order button moved out of the nav bar to a round button beside it. Requested in review.
- The plus button now opens a New sheet with Sale order (S05) and Production (S16, or Assign on a waiting order), so starting production is as quick as starting a sale. Accessible name changed to "New sale or production". Requested in review.
- Sample names: the owner is Sabreen and the employee is Ali (Ali Khan). Requested in review.
- Staff moved into S18 Settings: the page is now a sub-page with a back button and no bottom navigation, and the plus button is gone. Requested in review.
