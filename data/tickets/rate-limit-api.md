---
id: SYN-103
title: Rate limit the public search API
---
## Summary
The public /search endpoint is getting hammered. Add rate limiting etc.

## Acceptance criteria
- Requests over the limit return 429.
- Limit should be configurable.

## Notes
Probably use the existing Redis. Might need to coordinate with the mobile team since their app retries aggressively. Limit TBD, maybe 100/min or so?
