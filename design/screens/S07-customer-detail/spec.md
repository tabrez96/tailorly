---
id: S07
name: Customer detail
purpose: A customer's details, measurements and orders
size: 390x844
---

## Content and actions
- Phone (tap to call), customer since, notes. Edit (top) changes name, phone, notes.
- Spent (all orders) and To collect (open balances).
- Measurements: one set per garment type (Blouse, Kurta, Salwar...), with date updated. Edit opens states/edit-measurements.html; + Add garment starts a new set from a default list of fields for that garment.
- Orders for this customer, newest first. Tap opens S04.
- + New order for this customer opens S05 with the customer filled in.

## States
- Main (screen.html).
- Edit measurements (states/edit-measurements.html): units inches or cm, one field per measurement, + Add measurement for custom fields.
- No measurements yet: "No measurements yet." with + Add garment.
- No orders yet: "No orders yet." with the New order button.
- Dark theme (states/dark.html): same layout and content, dark tokens. Shown when the device is set to dark.

## Notes and open questions
- Measurements are kept per garment type because a blouse and a kurta need different fields. Old values are overwritten; the date shows how fresh they are.
- Open: whether to keep a history of past measurements. Not in the first version.

## Change log
- First version, from the approved brief.
- Primary colour changed from indigo to mulberry, and a dark theme added (states/dark.html); colours now come from theme tokens in ux.md. Requested in review.
- Restyled for a more modern look: Plus Jakarta Sans replaces the system font; large-title header, pill buttons and chips, tonal secondary buttons, softer card shadows, floating icon navigation. Layout, copy and flows unchanged. Requested in review.
