---
id: S13
name: Payments
purpose: Owner: money received per day, week or month, and who still owes what
size: 390x844
---

## Content and actions
- Header: Back, overline Reports, title Payments. Reached from Payments in S18 Settings and the report row.
- Report row, Payments selected. Period: Day, Week, Month (default), previous and next.
- Headline: received in the period, number of payments, still to collect (all open balances, not only this period).
- By method: Cash, UPI, Card, Bank, with count and amount.
- To collect: split into not yet delivered and delivered but still owing.
- Owing longest: delivered orders with a balance, oldest first, with days since delivery. Tap opens S04.

## States
- Main: this month (screen.html).
- No payments in the period: "No payments received in this period."
- Nothing to collect: "Everyone has paid." in the To collect card; Owing longest hidden.
- Loading: grey card outlines.
- Dark theme (states/dark.html).

## Notes and open questions
- Received is by payment date, so an advance counts on the day it was taken, not when the order is delivered.

## Change log
- First version: payments and money to collect. Requested in review.
- Reports moved into S18 Settings: back button added. Requested in review.
