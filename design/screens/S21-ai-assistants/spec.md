---
id: S21
name: AI assistants
purpose: Owner: connect an AI assistant to the shop through the MCP server, choose what it can see and do, and manage access keys
size: 390x1300
---

## Content and actions
- Header: Back (to S18), overline Settings, title AI assistants. Opened from MCP server in S18 Settings. Owner only; the employee never sees it.
- **MCP server** card: MCP server switch (On or Off, with "2 apps connected"), one line on what it does, and when on the Server address (read-only, with Copy) and a hint to paste it into the assistant's MCP or connector settings with an access key.
- **What it can see** (one switch each, all apply to every key):
  - Orders and customers (items, due dates, status, notes). On by default.
  - Measurements and photos. On by default.
  - Invoices and payments (prices, payments, money to collect, costs and gains per item and order). On by default.
  - Staff and pay (attendance, overtime, payouts). Off by default.
- **What it can do**: segmented control, Only read (default) or Read and change. Read and change lets the assistant create orders, record payments and update item measurements; it can never delete anything or record a payout. Switching to Read and change asks to confirm: "Let assistants make changes? Changes show in Recent activity."
- **Access keys**: one per connected app (name, date made, last used). + New key asks for a name ("Claude on tablet"), then shows the key once (states/new-key.html) with Copy key and Done. Revoke asks to confirm ("Revoke Claude on phone? That app stops working at once.") and removes the key.
- **Recent activity**: the last 20 things assistants did, newest first: what, which key, when, and a Read or Change chip. Changes link to the order (S04).

## States
- Main: MCP on, two keys, read only, staff and pay hidden (screen.html).
- New key (states/new-key.html): the key shown once, with a warning that it won't be shown again.
- Off / first run (states/off.html): switch off, no address, keys or activity; empty card "No assistant connected" with Turn on MCP server. Turning off keeps the keys but every app stops at once.
- Loading: card and list skeletons; switches disabled until settings load.
- Error: saving a switch fails, the switch returns to where it was and "Couldn't save. Check your connection and try again." shows under it (role="alert"). Copy fails: "Couldn't copy. Press and hold the address to copy it."
- No activity yet: "Nothing yet. Activity shows here once an app uses its key."
- Dark theme (states/dark.html).

## Notes and open questions
- Moved out of S18 so Settings can be a short list of everything; this page is set up once and rarely visited.
- What it can see and do is set once for all keys, to keep it simple for one shop; per-key access can come later if needed.
- Read only is the default, and Staff and pay is off, because an assistant reading pay is the most sensitive case.
- The employee's login never reaches the MCP server; keys belong to the owner.
- Server address is sample data; the real one depends on where the app is hosted.
- Open: which assistants the shop will connect first, and whether Read and change is wanted in the first version.

## Change log
- New screen: the MCP settings that were on S18 (switch, server address, what it can see and do, access keys, recent activity) moved here unchanged, with their states (new-key, off, dark). The account section stays on S18. Requested in review.
