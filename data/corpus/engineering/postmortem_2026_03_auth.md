# Postmortem: Auth Service Outage (ERR-5002)

**Owner:** Engineering · **Sensitivity:** Confidential · **Audience:** Engineering

- **Incident ID / error code:** ERR-5002
- **Date:** 8 March 2026
- **Severity:** SEV1
- **Duration:** 18 minutes (09:12–09:30 IST)

## Impact
The authentication service rejected all login attempts. For 18 minutes there was a **100%
login failure rate**; already-authenticated sessions were unaffected.

## Root cause
The TLS certificate used by the auth service's internal endpoint **expired**. Because
certificate renewal was a manual process, no one was alerted before expiry.

## Resolution
A new certificate was issued and deployed. **Automatic certificate renewal** (cert-manager)
was enabled for all internal endpoints.

## Action items
1. Add expiry alerts at 30, 14 and 7 days for every certificate.
2. Audit all services for remaining manually managed certificates.
