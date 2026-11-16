---
id: S20
name: Add item
purpose: Add one garment to a new order, or change it, with its product, price, options, measurements, materials, notes and photos
size: 390x1600
---

## Content and actions
- Header: back (returns to S05 without saving; asks first if anything was changed), overline "New order · <customer>", title Add item. When an existing item is opened from S05 the overline is "New order · Item 1 of 3" and the title is the product name (states/edit.html).
- Type: Custom or Ready-made (segmented control). It filters the product picker.
- Product: the chosen product with its photo, type and summary, and Change, which opens the product picker (S15 products of this type; Manage products opens S15). Choosing a product fills the price and shows its options and measurement fields.
- Price (₹): filled with the usual price, editable for this order only.
- Options (custom): the product's options, Yes or no as a No/Yes switch, Choice as chips. An option that uses a material says which one and when its quantity is asked (at order or when done), and adds a line to Materials.
- Measurements (custom): all the product's measurement fields as tiles, copied from the customer's saved set for that garment, with the date it was copied. Edit opens the measurement form for this item only (S04 states/edit-measurements.html, with "Also update Meera's saved set"). If the customer has no saved set, the tiles are replaced by Add measurements.
- Materials: this item's material lines (name, quantity, cost and selling price, On bill or Not billed chip). Option materials appear here with "length when done". + Add material opens the add-material sheet (S04 states/add-material.html) for this item.
- Notes for this item, and Photos for this item (+ Add takes a photo or picks one; the first photo is the item's picture everywhere).
- Bottom bar: the item price plus billed materials, and Add to order, which returns to S05 with the item in the list. In edit, the bar has Remove item (asks to confirm) and Save item.

## States
- Main: adding a custom Blouse (screen.html).
- Ready-made (states/ready-made.html): product and price only, a note that ready-made items have no measurements, options or estimate, an empty materials line "No materials for this item.", notes and photos.
- Edit (states/edit.html): an existing item opened from S05; Remove item and Save item.
- Error (states/error.html): price left empty; alert summary and the inline message "Enter a price. The usual price for a Blouse is ₹1,800." Focus moves to the price field.
- Product with no options: the Options section is hidden.
- Dark theme (states/dark.html).

## Notes and open questions
- A full page rather than a sheet because a custom item has up to four sections (options, measurements, materials, photos) and is the longest part of taking an order; a page keeps S05 short and readable.
- The estimate stays on S05 under Making it, next to Assign to, because it depends on who makes the order and where it lands in the queue.
- After the order is created, the same item is shown on S19 Item detail.

## Change log
- First version: adding and editing an item during order creation moved from inline cards on S05 to its own page. Requested in review.
