# Postmortem: Payment Gateway Timeout (ERR-4021)

**Owner:** Engineering · **Sensitivity:** Confidential · **Audience:** Engineering

- **Incident ID / error code:** ERR-4021
- **Date:** 14 January 2026
- **Severity:** SEV1
- **Duration:** 42 minutes (14:03–14:45 IST)

## Impact
The payments service returned timeouts for all checkout requests. Approximately **1,300
transactions failed** during the window. No data was lost; failed payments were not charged.

## Root cause
The payments service exhausted its database **connection pool**. A traffic spike combined
with a slow downstream query held connections open, and the pool size of **20** was too
small to absorb the load.

## Resolution
The connection pool size was increased from **20 to 50**, and a statement timeout of 2
seconds was added to the slow query.

## Action items
1. Add an alert when pool utilisation exceeds 80%.
2. Load-test the payments path at 3x peak before the next sale event.
