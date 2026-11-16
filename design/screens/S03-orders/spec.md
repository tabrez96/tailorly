---
id: S03
name: Orders
purpose: Find any order and see its status and balance
size: 390x844
---

## Content and actions
- Search by customer name, phone or order number.
- Filter chips: Open (not ready yet), Ready (waiting for pickup), Delivered, All. Open is the default. A Rework chip (shown only when any rework is not finished) lists delivered orders with rework open; their rows carry a Rework open chip.
- Each row: order number, customer, items, assigned employee, due date, status chip, balance due or "Paid". Tap opens S04.
- + New order (tonal pill in the header) opens S05. Holding the Orders tab from any owner screen does the same.
- Bottom navigation (owner): Today S02, Orders S03, Customers S06, Products S15, Production S12. A short tap opens the tab. Press and hold a tab (500 ms) to open its create page: Orders opens S05 New order; Customers opens the add customer form on S06; Products opens an empty product sheet on S15; Production opens S16 Work plan with the assign sheet (states/assign.html) for the waiting order with the earliest due date. Today has no hold action. Each tab also keeps a visible button in its header (+ New order on S03, + Add on S06 and S15, Assign on S12 and S16), so holding is never the only way.

## States
- Main: open orders (screen.html).
- Empty: no orders yet (states/empty.html).
- No search results: "No orders match "<text>"." with a Clear search link.
- Loading: grey row outlines.
- Error loading: "Couldn't load orders. Check your connection." with Try again.
- Dark theme (states/dark.html): same layout and content, dark tokens. Shown when the device is set to dark.

## Notes and open questions
- Status flow: Open, In progress (set automatically when the employee starts timing an item), Ready, Delivered.
- Ready-made items appear in orders like custom items, tagged "Ready-made". A ready-made-only sale is created as Delivered.
- Overdue orders: due date shown in the warning colour with "Overdue".

## Change log
- First version, from the approved brief.
- Primary colour changed from indigo to mulberry, and a dark theme added (states/dark.html); colours now come from theme tokens in ux.md. Requested in review.
- Restyled for a more modern look: Plus Jakarta Sans replaces the system font; large-title header, pill buttons and chips, tonal secondary buttons, softer card shadows, floating icon navigation. Layout, copy and flows unchanged. Requested in review.
- New order moved from the floating saffron pill to a 56 px round saffron plus button raised in a notch of the bottom navigation, between Orders and Customers. Requested in review. Products pill added to the header, leading to S15.
- Added a Free filter chip for free (self or family) orders. New order button moved beside the nav bar. Requested in review.
- The plus button now opens a New sheet with Sale order (S05) and Production (S16, or Assign on a waiting order), so starting production is as quick as starting a sale. Accessible name changed to "New sale or production". Requested in review.
- Added the Rework filter for delivered orders with rework open. Requested in review.
- Sample names: the owner is Sabreen and the employee is Ali (Ali Khan). Requested in review.
- Owner navigation is now Today, Orders, Production, Customers, Products; the round plus button and the New sheet are gone; Staff and Reports moved into S18 Settings. Requested in review. The Products pill in the header is replaced by + New order, since Products has its own tab.
- Owner navigation reordered to Today, Orders, Customers, Products, Production; the Production tab now opens S12, and holding it opens S16 with the assign sheet. Requested in review.
- Header: the title Orders and + New order now share one row (title on the left, pill at its natural width on the right), with any overline above both. Same header rule on every screen. Requested in review.
