---
id: S19
name: Item detail
purpose: Everything about one item (order line) of a sale order: its photos, product, options, measurements, notes, materials, production and gain
size: 390x844
---

## Content and actions
- Opened from the chevron on an item card in S04 (and from an item summary in S07's order list). Owner only; the employee sees the same item without prices in the S08 item details sheet.
- Header: Back (to S04), overline with the order number, customer and "item 1 of 2", the garment as the title, Edit (opens S04's edit for this item: product, price, options, notes).
- Photos: the first photo full width (170 to 190 px) with a "1/3" badge, then a strip of the others and + Add (camera or gallery). Tapping a photo opens it full screen. No photo: camera placeholder on `--sunk` and + Add photo.
- Summary card: number, garment, Custom or Ready-made chip, the product it came from with its usual price, the price on this order; status chip, who is on it, time logged against the estimate, due date.
- Options: each answer of the product's options (Lining Yes, asked when done; Sleeve style Elbow; Padding No).
- Measurements (custom only): the item's own copy as tiles, 3 per row, using the fields set on the product in S15; where they were copied from; Edit opens the S04 edit-measurements sheet for this item.
- Notes for the employee.
- Materials: this item's material lines (material, quantity and unit, bill or in the price, date, cost price) with the total cost; + Add material opens the S04 add-material sheet with this item already chosen.
- Production (custom only): time against the estimate and sessions; opens S17.
- Rework (Ready or Delivered orders with reworks on this item): the item's reworks as on S04, with + Add rework.
- Cost and gain for this item: price, staff time, materials, running costs, Gain on this item with its share of the price; marked estimated until the item is finished.
- Bottom bar: + Add material and Open order (back to S04).

## States
- Main: custom blouse in progress (screen.html).
- Ready-made item (states/ready-made.html): no measurements, options or production; materials hold what the shop paid for it; gain is price minus materials.
- No materials: "No materials yet." with + Add material.
- No measurements: "No measurements yet for this blouse." with Add measurements.
- Free order: price shown struck through as Usual price, Cost to the shop instead of Gain.
- Loading: grey card outlines.
- Dark theme (states/dark.html).

## Notes and open questions
- S04 keeps the full item cards, so the order can still be read in one scroll; S19 is the focused view of one garment, for checking it at the counter or showing the customer the photos.
- Prices, materials costs and gain are owner only.

## Change log
- First version: an item view for a sale order, with materials on the item. Requested in review.
