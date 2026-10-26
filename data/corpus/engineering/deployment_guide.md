# Deployment Guide

**Owner:** Engineering · **Sensitivity:** Internal · **Audience:** Engineering

## Pipeline
Deployments run through **GitHub Actions**. A merge to `main` builds an image, runs tests,
and promotes through staging to production.

## Deploy windows
Standard production deploys happen on **Tuesdays and Thursdays at 14:00 IST**. Deploys
outside these windows require an approved change request, except for SEV1 hotfixes.

## Rollout strategy
Releases use a **canary**: traffic shifts **5% → 50% → 100%**, with automated health checks
between steps. If error rate exceeds 1% at any step, the rollout halts automatically.

## Rollback
Any release can be **rolled back in under 5 minutes** by re-pointing the blue-green switch to
the previous version.

## Database changes
All migrations must be **backward compatible** (expand-then-contract). Schema changes are
deployed separately from and before the code that uses them.
