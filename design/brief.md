# Tailorly
## Problem
A small tailoring shop that makes custom clothes and also sells ready-made clothes keeps customers, measurements, orders, invoices, staff time and staff pay in separate places (or on paper). The owner wants one place for all of it. Scale: one shop, about 1 employee, about 100 orders a month.
Evidence: the owner's own requirements and answers. No independent demand data was gathered; this is a validated-by-the-owner idea, not a market-validated one.
Existing tailoring apps checked earlier (Atelierware, Tailor Trak, Thimblely): none found that combine per-item staff time, overtime and wages with INR invoicing. Search was not exhaustive.

## Users & buyer
- Owner (admin login): pays, runs the shop, sees everything.
- Employee (second login): sees assigned work, logs time, records day start/end, sees their own pay.
- Web app, designed phone first. Single shop. English only.

## Competition
Atelierware, Tailor Trak, Thimblely and similar tailoring/measurement tools cover customers and measurements; none found cover staff time per work item, overtime and weekly wages together with INR invoicing. Generic invoicing and HR tools exist but do not hold measurements or garment orders. Not exhaustively verified.

## MVP scope
- Customers: details, measurements, notes.
- Orders/sales (custom and ready-made; ready-made is sales only, no stock counts): create a sale, assign it to an employee, attach garment photos.
- Order materials: fabric items such as lining or falls with quantity/length, entered or updated later when bought or when the order is marked done; cost recorded there.
- Invoices: payments received against each invoice, with the date of each payment, balance outstanding.
- Employees: add with daily wage.
- Attendance: owner and employee can both record start and end of day.
- Employee time tracking per work item: start, pause, switch, resume, end.
- Pay: weekly payout, calculated per day worked (about 6 working days a week); a day off is unpaid. Employee can see what they were paid and when.
- Overtime: hours beyond 8 in a day, from start/end of day records. Hourly rate = daily wage / 8 (800/day = 100/hour). Overtime pay = overtime hours x hourly rate x multiplier (multiplier is a setting; the owner's example, 2 extra hours = 200, implies 1x).
- Reports: sales per customer (default); profit per customer and per sale.
- Currency INR; no GST/VAT.

## Out of scope
- Customer payment reminders (lowest priority; after first release; channel undecided: SMS, WhatsApp or Telegram).
- Tax (GST/VAT).
- Ready-made inventory counts.
- Multiple shops / multi-tenant.
- Languages other than English.
- Native mobile apps.

## Pricing hypothesis
Not defined by the owner; the product is for one shop. If it is ever offered to others, a flat monthly fee per shop would be the first thing to test. No evidence to support a number.

## Success metrics
- The owner runs all orders, invoices, attendance and weekly pay in the app, with no parallel paper or spreadsheet, for a full month.
- Weekly pay and overtime calculated by the app match the owner's own calculation.
- Employee logs time against work items on most working days.
- Profit per sale and per customer reports are trusted by the owner.

## Risks
- Name: Tailorly was found to be in use by other apps, tools or repos in an earlier search. The owner chose it knowingly; domain and trademark checks are theirs.
- Profit allocation: profit = sale minus expenses (bills and salaries), but how salaries are attributed to a single sale or customer is undefined. Proposed default: attribute staff cost by logged time per order, plus fabric/material costs on the order; shop-level bills shown at the shop level. Needs the owner's confirmation.
- Employee adoption of per-item time logging (start/pause/switch) on a phone.
- Overtime multiplier: example implies 1x; kept as a setting.
- Public holidays, part days and advances against pay are not specified; treated as out of scope until raised.
- Scope: everything listed is day one, which is large for a small team; the Architect may need to split releases.

## Runner-up ideas
None; this is the owner's own idea and there was no Scout research.

## Added since approval
- MCP server for AI assistants, configured on a Settings page (S18): on/off, what an assistant can see, read-only or read-write, keys (added 2026-11-15)
- Cost and gain per item and per order: staff time, materials and running costs against the price (added 2026-11-15)
- Rework after delivery: log alterations on a delivered order; never invoiced, their cost comes off the gain (added 2026-11-15)
- Primary and Secondary products: a product is sold directly (Primary) or used as material on an order (Secondary) (added 2026-11-16)
- Materials per item, picked from Secondary products, with cost price and selling price (added 2026-11-16)
- Products have two kinds: primary (sold) and secondary (materials with a unit, cost price and selling price); materials are added per item and per rework from the secondary products, optionally billed to the customer (added 2026-11-16)
- Item detail view for one line of a sale order (S19): photos, options, measurements, materials, production and gain (added 2026-11-16)
- Send the invoice to the customer on WhatsApp, offered when an order is marked ready and from a Ready or Delivered order (added 2026-11-16)

