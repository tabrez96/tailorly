---
id: S01
name: Sign in
purpose: Sign in as the owner or the employee
size: 390x844
---

## Content and actions
- Logo, product name, one-line tagline.
- Phone number and password fields, Sign in button. The account decides the role: the owner lands on S02, the employee on S08.
- Help line: employees who forget their password ask the owner, who resets it in S10 (states/edit-employee.html).

## States
- Main: filled form (screen.html).
- Error: wrong phone or password, alert above the form and both fields marked (states/error.html). The alert does not say which field is wrong.
- Loading: the Sign in button shows "Signing in..." and is disabled.
- Dark theme (states/dark.html): same layout and content, dark tokens. Shown when the device is set to dark.

## Notes and open questions
- One sign-in for both roles keeps it to one screen.
- Open: how the owner recovers a lost password (no email in scope). Proposed: reset from the server by whoever hosts the app.

## Change log
- First version, from the approved brief.
- Logo mark replaced with the button mark (tape measure dropped at review).
- Logo mark replaced with the shirt mark (button mark found unappealing at review; clothing asked for instead).
- Logo mark replaced with the lapel mark on a gradient tile (shirt mark found old-fashioned at review; a modern mark asked for).
- Primary colour changed from indigo to mulberry, and a dark theme added (states/dark.html); colours now come from theme tokens in ux.md. Requested in review.
- Restyled for a more modern look: Plus Jakarta Sans replaces the system font; large-title header, pill buttons and chips, tonal secondary buttons, softer card shadows, floating icon navigation. Layout, copy and flows unchanged. Requested in review.
