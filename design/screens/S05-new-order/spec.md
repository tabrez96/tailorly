---
id: S05
name: New order
purpose: Create a custom or ready-made order for a customer
size: 390x1480
---

## Content and actions
The order is made on one scrolling page in four numbered sections, so the whole order can be checked before it is created. Items are added and edited on their own page, S20.
- Header: back, overline "Sale order", title New order. Reached from + New order in the S03 header, by holding the Orders tab on any owner screen, and from New order on S07 (customer already chosen).
- 1 Customer: the chosen customer (name, phone, number of orders) with Change; or a search field (name or phone). + New customer opens a short form (name, phone, notes; measurements can be added later in S07). Who pays: Customer (default) or Free: self or family (states/free.html).
- 2 Items: one row per item (order line): first photo 52 px (camera placeholder if none), number, product name, Custom chip or Ready-made chip, a one-line summary (options answered, number of measurements, materials, notes), price, chevron. Tapping a row opens S20 for that item (states/edit.html). + Add item opens S20 empty. Measurements, options, materials, notes and photos live on the item, never on the order.
- 3 Making it: due date; Assign to (defaults to the only employee, or Not assigned yet) with a hint saying where the order lands in the queue and a link to S16; Your estimate to make it, one time field per custom item (hours and minutes), pre-filled with the usual time for that product, saved on the item and compared with logged time in S12 and S17. Ready-made items have none. An order with only ready-made items hides this section and is saved as Delivered.
- 4 Payment: advance received and method (Cash, UPI, Card, Bank), recorded as the first payment on the invoice; a summary card with the items total, the advance and the balance after this.
- Bottom bar: running total and number of items, and Create order. Creating opens the new order in S04.

## States
- Main: filled order with three items (screen.html).
- Free order (states/free.html): Who pays set to Free: self or family, with a note that nothing is charged; item prices show as usual price; Payment section is replaced by a card with the usual price and Charged ₹0; the bar says Free, not charged and the button is Create free order.
- Error (states/error.html): no customer and no items; alert summary (role="alert"), inline messages on the customer field and the items section. Focus moves to the first field with an error.
- No items yet: the items section shows "Add at least one item." only after Create order is pressed (error state); before that it shows only + Add item.
- Saving: Create order shows "Creating..." and is disabled.
- Dark theme (states/dark.html): same layout and content, dark tokens.

## Notes and open questions
- Each item keeps its own measurements, notes and photos, because one order often has different garments (a blouse and a chudidar).
- Ready-made items need no measurements, employee or due date; an order with only ready-made items hides those fields and is saved as Delivered.

## Change log
- First version, from the approved brief.
- Primary colour changed from indigo to mulberry, and a dark theme added (states/dark.html); colours now come from theme tokens in ux.md. Requested in review.
- Restyled for a more modern look: Plus Jakarta Sans replaces the system font; large-title header, pill buttons and chips, tonal secondary buttons, softer card shadows, floating icon navigation. Layout, copy and flows unchanged. Requested in review.
- Custom items now show their measurement tiles inline (first 6, Show all 9) with Edit, instead of a View link, to match S04. Requested in review.
- Notes and photos moved from order details into each item card; folded items show a summary. Example order now has two custom items with different measurement sets (Blouse, Chudidar) and a ready-made dupatta. Requested in review.
- Garment field became a product picker from S15; the item shows the product's options (Lining, Sleeve style, Padding on the Blouse). Requested in review.
- Added Who pays (Customer, or Free: self or family) and a free order state (states/free.html): Usual price, no advance, Create free order. Assign to shows where the order lands in the queue, with a link to S16. Requested in review.
- Added Your estimate to make it, one field per custom item, under Assign to. Requested in review.
- Each custom item has its own Materials list and + Add material; there are no order-level materials. Sample names: the owner is Sabreen and the employee is Ali (Ali Khan). Requested in review.
- Reworked into one clear order-creation page with numbered sections (Customer, Items, Making it, Payment) and a balance summary; items are now compact rows that open the new Add item page (S20) instead of long inline cards. Payment methods now include Card and Bank. Render height raised to 1480 so the whole page shows. Requested in review.
- Entry points: + New order on S03 and press and hold on the Orders tab replace the New sheet. Requested in review.
