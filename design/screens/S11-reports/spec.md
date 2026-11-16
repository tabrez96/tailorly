---
id: S11
name: Reports
purpose: Owner: sales per customer, and profit per customer and per sale
size: 390x844
---

## Content and actions
- Header: Back (to S18), title Reports. Reached from Reports in S18 Settings (each report row there opens its report). A sub-page with no bottom navigation; the report row switches between S11 to S14.
- Report row (chips, scrolls sideways): Sales (default), Profit, Production (S12), Payments (S13), Staff (S14).
- Sales grouped By customer (default) or By garment (count and sales per garment type).
- Period picker: this month (default), last month, this week, custom range.
- Sales: total sales for the period, orders, customers, still to collect; sales by customer, highest first. Tap a customer opens S07.
- Profit (states/profit.html): sales minus materials, staff pay and shop bills. Profit by Customer or by Sale. Tap a sale opens S04.
- Free work and reworks on Profit (states/profit.html): one list with two lines. Free work: count, usual price not charged, cost to the shop; tap opens S03 filtered to Free. Reworks: count, minutes and cost for the period (staff time + materials; never invoiced); tap opens S03 on the Rework filter for the period. A line with nothing in the period reads "None in November 2026".
- Profit by Garment (states/by-garment.html): for each product sold in the period, the count, average price, average cost (staff, materials, running costs) and gain per piece in rupees and percent, with a stacked bar; tap opens S03 filtered to that garment.
- Running costs card (on Profit by Garment): the rate per hour of work and how it is made; Edit opens a sheet (states/running-costs.html) with monthly estimates (Rent, Electricity, Thread, needles and buttons, + Add a cost) and working hours a month (default 208 = 26 days x 8). The rate is the monthly total / hours, rounded to the rupee; it applies to orders not yet delivered and to new ones. Until set, it is pre-filled from the average of the shop bills of the last 3 months.
- Shop bills: rent, electricity and other shop costs with date and amount; + Add bill (name, amount, date).

## States
- Main: sales by customer (screen.html).
- Profit (states/profit.html).
- Profit by Garment with the running costs card (states/by-garment.html); running costs sheet (states/running-costs.html).
- Running costs not set and no bills yet: the card reads "Add your monthly running costs to see the full cost of each garment." with Add, and gains leave running costs out (said under the list).
- No sales in the period: "No sales in November 2026."
- Loading: grey outlines.
- Dark theme (states/dark.html): same layout and content, dark tokens. Shown when the device is set to dark.

## Notes and open questions
- Profit per sale and per customer counts materials and staff time logged to that order. Pay not logged to any order, and shop bills, are counted only in the shop total. This is the proposed rule from the brief; to be confirmed with the owner.

## Change log
- First version, from the approved brief.
- Primary colour changed from indigo to mulberry, and a dark theme added (states/dark.html); colours now come from theme tokens in ux.md. Requested in review.
- Restyled for a more modern look: Plus Jakarta Sans replaces the system font; large-title header, pill buttons and chips, tonal secondary buttons, softer card shadows, floating icon navigation. Layout, copy and flows unchanged. Requested in review.
- The key card now uses the mulberry hero gradient (see Design system).
- Sales and Profit tabs replaced by a report row (Sales, Profit, Production, Payments, Staff) leading to S12, S13 and S14; Sales can be grouped by customer or by garment. Requested in review.
- New order moved from the floating saffron pill to a 56 px round saffron plus button raised in a notch of the bottom navigation, between Orders and Customers. Requested in review.
- Profit tab (states/profit.html): added a Free work card with the number of free orders, the usual price not charged and the cost to the shop; tap opens S03 filtered to Free. New order button moved beside the nav bar. Requested in review.
- Profit by gains a Garment view with cost and gain per piece, and a Running costs rate (states/by-garment.html, states/running-costs.html); the Free work cost includes running costs. Requested in review.
- The plus button now opens a New sheet with Sale order (S05) and Production (S16, or Assign on a waiting order), so starting production is as quick as starting a sale. Accessible name changed to "New sale or production". Requested in review.
- Added the Rework after delivery card to Profit. Requested in review.
- The Rework after delivery card became a Reworks line (count, minutes, cost) beside Free work in one list; rework cost is staff time + materials, with no charges. Requested in review.
- Reports moved into S18 Settings: back button, no bottom navigation, plus button gone. Requested in review.
