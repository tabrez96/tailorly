---
id: S15
name: Products
purpose: Owner: keep the preset garments the shop makes and sells, with their usual price and options
size: 390x844
---

## Content and actions
- Header: title Products, + Add (opens the product sheet empty). Products is a tab in the owner bottom navigation; holding the tab on any owner screen opens the same empty sheet.
- Bottom navigation (owner): Today S02, Orders S03, Customers S06, Products S15, Production S12. A short tap opens the tab. Press and hold a tab (500 ms) to open its create page: Orders opens S05 New order; Customers opens the add customer form on S06; Products opens an empty product sheet on S15; Production opens S16 Work plan with the assign sheet (states/assign.html) for the waiting order with the earliest due date. Today has no hold action. Each tab also keeps a visible button in its header (+ New order on S03, + Add on S06 and S15, Assign on S12 and S16), so holding is never the only way.
- Kind, a segmented control at the top: Sold (primary products, sold to customers) and Materials (secondary products, used to make garments), with counts. Materials list (states/materials.html): name, selling price or "not billed on its own", what uses it, cost price per unit, chevron; tapping opens the material sheet (states/edit-material.html): Name, Kind, unit (m, pcs, pair, set), Cost price and Selling price per unit, Bill it by default (off: it comes with the garment price), Remove, Cancel, Save.
- Search by product name; filter chips All, Custom, Ready-made, with counts.
- One list row per product: icon tile (garment for Custom, bag for Ready-made), name, type chip, options summary ("3 options: Lining, Sleeve style, Padding" or "No options"), usual price, chevron. Tapping a row opens the product sheet (states/edit-product.html).
- Product sheet: Name, Price, Kind (Primary: sold, or Secondary: material; switching to Secondary turns it into a material), Type (Custom or Ready-made; Custom items carry the customer's measurements for this garment), and for Custom products the Measurements row: the measurement fields for this garment (count and names; Edit adds, removes or reorders fields; S07, S05, S04 and S19 use this list). Options, each on a sunken panel:
  - Option name (Lining, Sleeve style, Padding).
  - Answer: Yes or no, or Choice (with its list of choices, e.g. Short, Elbow, Full, Sleeveless).
  - If yes, it uses: a material from the secondary products (for example Lining uses Lining, cotton cream); its cost and selling price come from the material.
  - Asks for (toggle chips): quantity in the material's unit, notes. For a Yes or no option these are asked only when the answer is Yes.
  - Ask: At order (on S20, while adding the item) or When done (in the Mark ready sheet on S04, states/ready-options.html).
  - Remove option. Other options fold to a one-line summary with Edit; + Add option adds a new open panel.
- Sheet actions: Remove (product; asks "Remove Blouse? Past orders keep it."), Cancel, Save.

## States
- Main: 9 products, 7 custom and 2 ready-made (screen.html).
- Edit product sheet (states/edit-product.html): Blouse, with Kind, the Measurements row and Lining open, using Lining, cotton cream.
- Materials (states/materials.html): 6 secondary products.
- Edit material sheet (states/edit-material.html): Lining, cotton cream.
- Empty (states/empty.html): "No products yet" with + Add product.
- No search results: "No product called "sherwani". Add it?" with + Add product.
- Error in the sheet: missing name or price, or a Choice option with fewer than 2 choices; message under the field, alert summary, focus to the first error.
- Remove a product used in orders: confirm as above; the product leaves the list and the S20 product picker, past orders are unchanged.
- Dark theme (states/dark.html): same layout and content, dark tokens.

## Notes and open questions
- A nav tab, replacing Staff: products are opened often while taking orders and pricing. Manage products in the S20 product picker still opens it.
- An order item copies the product's name, price and option answers, so editing a product changes new orders only.
- Option answers that use a material become material lines of that item, so they count in the order's profit (S04, S11).
- "When done" is asked at Mark ready, when the lining or fall has been bought; Skip for now asks again at Mark delivered.
- Open: measurement fields per garment are not configurable here yet.

## Change log
- New screen: preset products with price and configurable options (Yes or no or Choice; asks for quantity, cost, notes; at order or when done). Requested in review.
- Two kinds of product: primary (sold) and secondary (materials, with unit, cost price and selling price), with a Sold and Materials switch, a materials list and a material sheet. Options use a material instead of asking for a cost. Measurement fields are set on each custom product. Requested in review.
- Product picker and option questions at order now live on S20 Add item, which replaced the inline item cards on S05. Requested in review.
- Products is now a tab in the owner bottom navigation (replacing Staff); back button removed. Requested in review.
- Owner navigation reordered to Today, Orders, Customers, Products, Production; the Production tab now opens S12, and holding it opens S16 with the assign sheet. Requested in review.
- Header: the title Products and + Add now share one row (title on the left, pill at its natural width on the right). Same header rule on every screen. Requested in review.
