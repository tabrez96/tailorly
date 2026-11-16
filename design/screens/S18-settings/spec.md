---
id: S18
name: Settings
purpose: Owner: one place for reports, staff, running costs, AI assistants and the account
size: 390x1180
---

## Content and actions
- Header: Back (to S02), title Settings. Opened from the round Settings (gear) button in the S02 Today header. Owner only; the employee never sees it.
- **Reports** (one row each, with a live one-line figure): Sales and profit (S11, "₹42,600 sold in November"), Production (S12, garments finished this week), Payments (S13, still to collect), Staff report (S14, days and overtime this week). Inside a report, the report row switches between them.
- **Shop**: Staff (S10: employee, pay day, a warning chip with the amount to pay this week), Running costs (opens the running costs sheet, S11 states/running-costs.html; shows the monthly amount and the rate per hour).
- **AI assistants**: MCP server row with its state ("On · 2 apps connected · only read" or "Off"); opens S21.
- **Account**: who is signed in (Sabreen, Owner), Change password (current and new password form), Sign out (to S01).
- App version at the bottom.

## States
- Main (screen.html).
- First run: report rows read "No sales yet", "Nothing finished yet", "Nothing to collect"; Staff reads "Add your first employee" and opens the S10 add form; MCP row reads "Off".
- Loading: row figures show grey bars; rows can still be opened.
- Error loading the figures: rows show without figures; the reports themselves say what went wrong.
- Dark theme (states/dark.html).

## Notes and open questions
- Settings holds what is set up once (staff, running costs, assistants, account) and what is checked about once a week (reports and pay), so the bottom navigation is kept for daily work: Today, Orders, Production, Customers, Products.
- Reports come first because they are the most visited part of Settings; the figures on each row answer the usual question without opening the report.
- Weekly pay stays reachable in one tap from the Staff pay card on S02.

## Change log
- New screen: Settings with the MCP server (on or off, address, what it can see and do, access keys, activity) and Account. Requested in review.
- Invoices and payments now also covers costs and gains, so an assistant can answer questions like "what did I make on blouses this month". Requested in review.
- Sample names: the owner is Sabreen and the employee is Ali (Ali Khan). Requested in review. The Account section shows who is signed in (Sabreen, Owner).
- Settings is now the hub for everything set up once or checked weekly: Reports (S11 to S14), Shop (Staff S10, Running costs), AI assistants (MCP, moved to its own screen S21) and Account. Requested in review.
