---
id: S16
name: Work plan
purpose: Owner: assign orders to employees and set the order each employee works in, starting from a suggested queue
size: 390x844
---

## Content and actions
- Bottom navigation (owner): Today S02, Orders S03, Customers S06, Products S15, Production S12. A short tap opens the tab. Press and hold a tab (500 ms) to open its create page: Orders opens S05 New order; Customers opens the add customer form on S06; Products opens an empty product sheet on S15; Production opens S16 Work plan with the assign sheet (states/assign.html) for the waiting order with the earliest due date. Today has no hold action. Each tab also keeps a visible button in its header (+ New order on S03, + Add on S06 and S15, Assign on S12 and S16), so holding is never the only way.
- Header: Back (to S12) on its own row, overline Production, then the title Work plan sharing its row with an Assign pill on the right, which opens the assign sheet (states/assign.html) for the waiting order with the earliest due date. The pill is hidden when every order is assigned (states/empty.html). A sub-page of the Production tab, which stays highlighted. Holding the Production tab on any owner screen opens this screen with the assign sheet (states/assign.html) for the waiting order with the earliest due date, or this screen alone when every order is assigned. Also opened from Work plan and Assign on S12, from Ali's queue on S12 (scrolled to that person) and from Give Ali work on S12 (the assign sheet for the earliest waiting order with that person already chosen). Also reached from the Work plan card on S02, Change on the Assigned to row in S04 and the Work plan link under Assign to in S05.
- Hero card, Suggested next: the top unstarted item in the employee's queue, with its photo, order and customer, and why it is next in one plain sentence (due date and time needed), plus whether every item fits before its due date.
- Not assigned: orders with no employee yet, newest due date last. Each row: photo, garment, order number, customer, due date, Free chip for free orders, and Assign, which opens the assign sheet (states/assign.html).
- Assign sheet: Who makes it (radio rows per employee, with how many items and hours are already in their queue), Your estimate to make it (hours and minutes per item, filled with the usual time for that product, which the owner can change), Place in queue (Suggested, with the position and when it would be ready; or Next up, right after the item they are on), and Assign to <name>. The same sheet opens from Change on S04.
- <Employee>'s queue: one section per employee, with item count and hours of work. Each row: rank, photo (tap opens S04), garment, order number, due date in bold when it is within 2 days, time needed, status chip, Moved by you chip if the owner moved it, and a 44 px drag handle.
- How it is sorted (one line above the list): started work first, then by due date, then shorter jobs first. Full rule in ux.md under Suggested work order.
- Reorder: drag the handle. Or tap the handle: the row is picked up and a bottom bar shows Up, Down and Done (states/reorder.html). Moved rows keep their place; everything else keeps following the suggestion.
- Banner when anything was moved: "You moved 1 item." with Back to suggested, which clears all moves for that employee.
- Rework after delivery (logged on S04) joins the queue of the person it was given to, as a row with a Rework chip and its reason, sorted by its due date and estimate like any item.
- The employee sees the same order in S08 Up next.

## States
- Main: one employee, 6 items in the queue, 2 orders not assigned, 1 item moved by the owner (screen.html).
- Assign sheet (states/assign.html).
- Reordering, an item picked up (states/reorder.html). Each move is announced politely: "Kurta moved to position 4 of 6."
- Nothing to plan: every item finished (states/empty.html), with New order.
- Nothing unassigned: the Not assigned section is hidden.
- Late risk: if an item can't be finished by its due date even in the best order, its row shows a red Late risk chip and the hero says "1 item won't make its due date. Move it up or talk to the customer."
- New employee with an empty queue: "Nothing in Sana's queue yet. Assign an order above."
- Loading: grey row outlines. Error saving a move: the row snaps back and an alert says "Couldn't save the new order. Check your connection and try again."
- Dark theme (states/dark.html).

## Notes and open questions
- Assignment is per order: all items of an order go to one person's queue, and the queue is per item, because items are what the employee times.
- Time needed in the queue is the owner's estimate for the item. The estimate field is pre-filled with the usual time for the product (average of the last 10 finished items, 2 hours until there are 3), so accepting it is one tap. The estimate can be changed until the item is started, then it is fixed so the comparison in S12 and S17 stays honest.
- A sub-page of the Production tab (S12): the tab shows how work is going, and Work plan or holding the tab gets to the queue in one step.
- Splitting one order between two employees is not in the first version.

## Change log
- New screen: assign orders and plan each employee's queue, with a suggested order that the owner can follow or change by hand. Requested in review.
- Assign sheet asks for the owner's estimate to make each item, pre-filled with the usual time; the queue uses it as time needed. Requested in review.
- New entry points: Production in the New sheet opens this screen, and Assign there opens the assign sheet directly. Requested in review.
- Rework jobs from S04 appear in the queue with a Rework chip. Requested in review.
- Sample names: the owner is Sabreen and the employee is Ali (Ali Khan). Requested in review.
- Now the Production tab in the owner bottom navigation: no back button, title Production, Report pill to S12; holding the tab opens the assign sheet. Fixed a garbled sentence in the hero and the Next up option. Requested in review.
- Owner navigation reordered to Today, Orders, Customers, Products, Production; the Production tab now opens S12, and holding it opens S16 with the assign sheet. Requested in review. Header changed to Back, overline Production, title Work plan; the Report pill is gone because S12 is the tab it comes from.
- Opened from Ali's queue and Give Ali work on the new live Production tab (S12); the assign sheet can open with the maker already chosen. Requested in review.
- Header: Back on its own row, overline Production, then the title Work plan sharing its row with a new Assign pill (opens the assign sheet for the earliest waiting order; hidden when nothing is waiting). Requested in review.
