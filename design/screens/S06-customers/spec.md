---
id: S06
name: Customers
purpose: Find a customer and see who owes money
size: 390x844
---

## Content and actions
- Search by name or phone.
- Alphabetical list: initials, name, phone, balance due or "Paid up", open orders count. Tap opens S07.
- + Add (header pill) opens a short form: name, phone, notes. Holding the Customers tab on any owner screen opens the same form.
- Bottom navigation (owner): Today S02, Orders S03, Customers S06, Products S15, Production S12. A short tap opens the tab. Press and hold a tab (500 ms) to open its create page: Orders opens S05 New order; Customers opens the add customer form on S06; Products opens an empty product sheet on S15; Production opens S16 Work plan with the assign sheet (states/assign.html) for the waiting order with the earliest due date. Today has no hold action. Each tab also keeps a visible button in its header (+ New order on S03, + Add on S06 and S15, Assign on S12 and S16), so holding is never the only way.

## States
- Main: list (screen.html).
- Empty: no customers yet (states/empty.html).
- No search results: "No customer matches "<text>"." with + Add "<text>" as a customer.
- Loading: grey row outlines.
- Dark theme (states/dark.html): same layout and content, dark tokens. Shown when the device is set to dark.

## Notes and open questions
- About 100 orders a month means a few hundred customers within a year; search is the main way in.

## Change log
- First version, from the approved brief.
- Logo mark replaced with the button mark (tape measure dropped at review).
- Logo mark replaced with the shirt mark (button mark found unappealing at review; clothing asked for instead).
- Logo mark replaced with the lapel mark on a gradient tile (shirt mark found old-fashioned at review; a modern mark asked for).
- Primary colour changed from indigo to mulberry, and a dark theme added (states/dark.html); colours now come from theme tokens in ux.md. Requested in review.
- Restyled for a more modern look: Plus Jakarta Sans replaces the system font; large-title header, pill buttons and chips, tonal secondary buttons, softer card shadows, floating icon navigation. Layout, copy and flows unchanged. Requested in review.
- The floating + Customer pill moved to a + Add pill in the header, so the bottom navigation can hold the New order plus button. Requested in review.
- New order button moved out of the nav bar to a round button beside it. Requested in review.
- The plus button now opens a New sheet with Sale order (S05) and Production (S16, or Assign on a waiting order), so starting production is as quick as starting a sale. Accessible name changed to "New sale or production". Requested in review.
- Owner navigation is now Today, Orders, Production, Customers, Products; the round plus button and the New sheet are gone; Staff and Reports moved into S18 Settings. Requested in review.
- Owner navigation reordered to Today, Orders, Customers, Products, Production; the Production tab now opens S12, and holding it opens S16 with the assign sheet. Requested in review.
- Header: the title Customers and + Add now share one row (title on the left, pill at its natural width on the right). Same header rule on every screen. Requested in review.
