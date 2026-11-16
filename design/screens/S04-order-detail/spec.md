---
id: S04
name: Order detail
purpose: Everything about one order: its items (each with measurements, notes and photos), materials, invoice and profit
size: 390x844
---

## Content and actions
- Customer (tap opens S07), due date, status chip (plus a Free chip for free orders) and status steps; Assigned to row with the employee and where the order sits in their queue; Change opens the assign sheet (see S16 states/assign.html).
- Each custom item shows logged time against its estimate ("2h 40m of 3h est.") and ends with a Production row (time, estimate, number of sessions) that opens S17 for that item.
- Items (the order lines), one card each, right under the customer. Each card: first photo, number, garment, Custom or Ready-made, price, item status (Not started, In progress, Finished), who is on it and time logged; then that item's own measurements (inches, tiles), where they were copied from, notes for the employee, and photos (tap to view full size, + Add for camera or gallery). Edit on an item's measurements opens a sheet for that item only (states/edit-measurements.html) with "Also update Meera's saved Blouse measurements" (on by default); Save updates this item and, if ticked, S07. Ready-made items show no measurements. + Add item adds another line.
- Materials belong to an item: each item card has a Materials list (material, quantity with its unit, whether it is on the bill or in the price, date bought, cost price) and + Add material for that item. There is no order-level Materials section. + Add material opens a sheet (states/add-material.html) that shows which item it is for (photo, number, garment; Change picks another item), then the material picked from the secondary products in S15 (search, the most used first, Show all, + New material), Quantity in the material's unit, Cost price and Selling price (both filled from the product for that quantity and editable), Add to the customer's bill (off by default: the garment price covers it; on adds the selling price as a line under that item on the invoice), and Bought on. Cost price can be left blank and filled later.
- Tapping the chevron in an item card header opens S19 for that item.
- Invoice: total, received, balance; each payment with date and method. Record payment opens a sheet (states/record-payment.html). On Ready and Delivered orders the invoice card has Send invoice (tonal, chat icon), which opens WhatsApp to the customer's number with a message ready to send: shop name, order number, the items and their prices, billed materials, total, received and balance, or Paid. Under it, "Last sent Sat 7 Nov" once it has been sent, otherwise "Opens WhatsApp with the invoice and balance". Without a phone number the button is disabled with "Add a phone number on S07 first."
- Cost and gain: for each item, its price, its cost (staff time + materials + running costs) and the gain in rupees and as a share of the price, with a stacked bar (staff, materials, running costs, gain) and the same split in words. Below, the order as a whole: sale, staff time, materials, running costs, Gain on this order. Until an item is finished its time is the estimate or the time logged, whichever is more, and the card says the figures are estimated.
- Bottom action moves the order to its next status: Mark ready, then Mark delivered. Mark ready opens the Mark ready sheet. If an item has product options asked when done (e.g. Lining: length and cost), the sheet asks for them first (states/ready-options.html); saved answers become material lines of that item. Skip for now marks it ready and asks again at Mark delivered. Every Mark ready sheet ends with a checkbox, Send invoice on WhatsApp, unticked by default, showing the customer's name, number and balance; ticked, marking ready opens WhatsApp with the invoice ready to send. When the customer has no phone number the checkbox is disabled with "Add a phone number on S07 first." (states/ready-no-phone.html).
- Rework after delivery (Delivered orders): a section under the items, headed with the total rework cost. The bottom action becomes + Add rework, which opens a sheet (states/add-rework.html): which item (radio rows, with who made it), Why (Fit alteration, Our mistake, Customer change, Repair), What to do (shown to the employee), Who does it (defaults to who made the item), Estimate (pre-filled with 45m, the usual rework time once there are 3 finished reworks), Due (defaults to 2 days from today), and Materials used: the same workflow as items, + Add material opens the add-material sheet for that rework (picked from the secondary products, quantity, cost price; the selling price is shown for reference and the bill switch is hidden because a rework is never billed); each line can be removed. Save rework adds it to the section and puts it in that person's queue (S16, S08). Reworks are never invoiced: no charge, no payment, no change to the balance.
- Rework row: R1, R2... with the item's photo and garment, reason chip, status (Not started, In progress, Finished), the date it was added, who, minutes spent (against the estimate while open), materials used (or "No materials") and its cost on the right; tap opens S17 for that rework. Cost = logged minutes x the employee's hourly rate + materials; while open it uses the estimate or the minutes logged, whichever is more, marked estimated. A header chip "Rework open" shows while any rework is not finished. The order stays Delivered; finished reworks stay listed. Item rows show the rework time added to the item's logged time ("3h 05m + 40m rework").
- Edit (top) changes items, prices, due date and notes.

## States
- Item with no materials: "No materials yet." and + Add material inside the item card.
- Free order (states/free.html): Free chip by the status, item price struck through, no Invoice section and no Record payment; a Free order card shows usual price not charged, materials, staff time, running costs and Cost to the shop.
- Main: in progress with part payment (screen.html).
- Edit measurements sheet (states/edit-measurements.html).
- Item with no saved measurements: inside that item's card, "No measurements yet for this kurta." and an Add measurements button that opens the same sheet.
- Item with no photo: camera placeholder in place of the thumbnail.
- Record payment sheet (states/record-payment.html). Amount defaults to the balance; date defaults to today.
- Add material sheet (states/add-material.html).
- Mark ready with options to fill (states/ready-options.html), with the unticked Send invoice on WhatsApp checkbox.
- Mark ready, customer has no phone number (states/ready-no-phone.html): no options to fill, the checkbox is disabled with "Add a phone number on S07 first."; Mark ready still works.
- Send invoice: on the Delivered states (states/rework-open.html, last sent; states/no-rework.html, not sent yet). If WhatsApp can't be opened on this device: "WhatsApp isn't available here. Copy the invoice text instead?" with Copy text.
- Delivered with reworks (states/rework-open.html): items folded to one-line rows, then Rework after delivery (R1 finished, R2 in progress, total -₹142), Invoice still Paid, and Cost and gain with Gain at delivery, Reworks (count, minutes, staff and materials) and the Gain on this order after rework.
- Delivered, no reworks (states/no-rework.html): the section reads "No reworks after delivery." and + Add rework stays in the bottom bar.
- Add rework sheet (states/add-rework.html). Error: "Say what needs doing so Ali knows." next to What to do when it is empty.
- Paid in full: balance shows "Paid" in green, Record payment is hidden.
- Mark delivered with a balance: confirm "Meera still owes 1,200. Mark delivered anyway?"
- Photo upload failed: thumbnail with "Upload failed. Tap to retry."
- Loading: grey card outlines.
- Dark theme (states/dark.html): same layout and content, dark tokens. Shown when the device is set to dark.

## Notes and open questions
- Send invoice uses a WhatsApp link (wa.me) with the invoice as text, so it needs no WhatsApp account set up in the app; the owner presses send in WhatsApp. Free orders have no invoice, so neither the checkbox nor Send invoice shows on them.
- Measurements belong to each item, not to the order: one order can hold a blouse and a chudidar, and each needs its own set. The item's copy is what the employee sees in S08, so a later edit in S07 never changes a garment already being cut.
- One invoice per order: the order total is the invoice; payments are recorded against it. Keeps 100 orders a month simple.
- Payment methods: Cash, UPI, Card, Bank. Method is for the owner's records only.
- Staff time cost = logged minutes x hourly rate (daily wage / 8), rounded to the rupee. Overtime is not added per order; it shows in shop-level staff pay (S11).
- Running costs = item time x the shop's running cost per hour (estimated monthly bills / working hours a month, set on S11 Profit). It is a rough share of electricity, thread, rent and so on, so the gain per item and per order can be compared with the price; the shop's real profit on S11 still uses the bills actually recorded.
- Rework is a separate job on an item, not a reopened item: the item stays Finished. Its minutes are added to the item's logged time and to the employee's pay like any work, but S17 and S12 compare the estimate with the first make only, shown separately from rework, so the estimate stays a fair comparison. Rework cost = logged minutes x hourly rate + materials; it carries no running-cost share, and it comes off the order's gain and the item's gain. Rework can be logged on Ready orders too (before pickup, after a trial).
- A ready-made item has no logged time, so its cost is its materials (purchase cost) only.

## Change log
- First version, from the approved brief.
- Primary colour changed from indigo to mulberry, and a dark theme added (states/dark.html); colours now come from theme tokens in ux.md. Requested in review.
- Restyled for a more modern look: Plus Jakarta Sans replaces the system font; large-title header, pill buttons and chips, tonal secondary buttons, softer card shadows, floating icon navigation. Layout, copy and flows unchanged. Requested in review.
- Added a Measurements card near the top (one tab per custom item, tiles in inches) and an edit sheet (states/edit-measurements.html). Measurements are the core of a custom order and were missing. Requested in review.
- Measurements, notes and photos moved from the order onto each item (order line): one card per item with its photo, status, time, measurements, notes and photos. Invoice lists the items; materials can be tagged to an item. Order-level Measurements, Notes and Photos sections removed. Requested in review.
- Added the Mark ready sheet for product options asked when done (states/ready-options.html). Requested in review.
- Assigned to is now a row with the queue position and Change, which opens the assign sheet from S16. Added a free order state (states/free.html): no invoice, usual price not charged and Cost to the shop instead of profit. Requested in review.
- Item cards show time against the owner's estimate and a Production row that opens S17. Requested in review.
- Cost and profit became Cost and gain: per item and per order, staff time + materials + estimated running costs against the price, with a stacked bar. The free order cost includes running costs. Requested in review.
- Added rework after delivery: + Log rework on delivered orders (states/log-rework.html), a Rework after delivery section and its cost in Cost and gain (states/rework-open.html). Requested in review.
- Rework after delivery moved under the items, with its total cost; each rework shows date, item, reason, minutes and materials. + Log rework became + Add rework (states/add-rework.html replaces states/log-rework.html) with Materials used and Cost; the charge switch is removed, reworks are never invoiced; rework cost is staff time + materials. Added the empty state (states/no-rework.html). Requested in review.
- Materials moved from the order into each item card, picked from secondary products with cost price and selling price and an Add to bill switch; the add-material sheet shows the item it is for. Rework uses the same material workflow. Items open S19. Sample names: the owner is Sabreen and the employee is Ali (Ali Khan). Requested in review.
- Added Send invoice on WhatsApp: an unticked checkbox on the Mark ready sheet (disabled without a phone number, states/ready-no-phone.html) and a Send invoice button in the invoice card on Ready and Delivered orders. Requested in review.
