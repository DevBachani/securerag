# On-Call Runbook

**Owner:** Engineering · **Sensitivity:** Internal · **Audience:** Engineering

## Rotation
On-call uses **PagerDuty** with a **primary and secondary** engineer. Rotation changes
**weekly**, handing over every Monday at 10:00.

## Severity levels and response targets
| Severity | Definition | Response target |
|---|---|---|
| **SEV1** | Full outage or data loss | **15 minutes** |
| **SEV2** | Major feature degraded | **1 hour** |
| **SEV3** | Minor/isolated issue | Next business day |

## Escalation
If the primary does not acknowledge within **30 minutes**, PagerDuty escalates to the
secondary, then to the engineering manager.

## During an incident
1. Acknowledge the page and open an incident channel.
2. Post updates to the public **status page** every 30 minutes.
3. Mitigate first, diagnose later.

## After an incident
A written **postmortem is required within 48 hours** for every SEV1 and SEV2. Postmortems
are blameless and action items are tracked to closure.
