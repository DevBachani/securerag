# Postmortem: Search Latency Spike (ERR-6210)

**Owner:** Engineering · **Sensitivity:** Confidential · **Audience:** Engineering

- **Incident ID / error code:** ERR-6210
- **Date:** 22 June 2026
- **Severity:** SEV2
- **Duration:** 1 hour 10 minutes (16:05–17:15 IST)

## Impact
Search response time degraded sharply. The **p95 latency rose to 3.5 seconds** (normal is
under 400 ms), and about **27% of search requests** were slower than 2 seconds. No requests
failed outright.

## Root cause
A new filter feature issued a query against the listings table that **lacked a supporting
index**, causing full table scans under load.

## Resolution
A **composite index** on (category, created_at) was added, returning p95 latency to ~350 ms.

## Action items
1. Require an EXPLAIN review for any new query in code review.
2. Add a slow-query dashboard with a p95 alert at 1 second.
