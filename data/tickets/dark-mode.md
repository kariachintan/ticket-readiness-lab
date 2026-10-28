---
id: SYN-105
title: Dark mode for settings page
---
## Summary
As a user, I want the settings page to respect my OS dark-mode preference so that it does not blind me at night.

## Acceptance criteria
- Given prefers-color-scheme: dark, when I open /settings, then the page uses the dark palette tokens.
- Given prefers-color-scheme: light, when I open /settings, then the page is unchanged from today.
- Contrast ratio for body text must be at least 4.5:1 in both modes.

## Out of scope
- A manual in-app toggle (tracked separately).
- Pages other than /settings.

## Edge cases
- OS preference changes while the page is open: re-render without reload.
- Users with forced-colors / high-contrast mode: do not override.
