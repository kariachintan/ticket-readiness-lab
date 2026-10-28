---
id: SYN-102
title: Password reset via email
depends_on: [SYN-099]
---
## Summary
As a signed-out user, I want to request a password reset link by email so that I can regain access to my account.

## Acceptance criteria
- Given a registered email, when I submit the reset form, then I receive an email with a single-use link within 2 minutes.
- Given an unregistered email, when I submit the form, then the UI shows the same confirmation message (no account enumeration).
- Given a reset link older than 30 minutes, when I open it, then I see an "expired" page with a link to request a new one.
- Given a link that was already used, when I open it, then I see the expired page.

## Out of scope
- SMS reset
- Admin-initiated resets

## Dependencies
- SYN-099 (transactional email provider integration) must be merged first.

## Notes
Rate limit: max 5 requests per email per hour (assumption - confirm with security).
