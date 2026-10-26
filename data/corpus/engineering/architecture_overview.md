# Architecture Overview

**Owner:** Engineering · **Sensitivity:** Internal · **Audience:** Engineering

## Shape of the system
Acme's product runs as **14 microservices** behind a single **API gateway**. Services
communicate synchronously over REST and asynchronously over a **Kafka** event bus.

## Data stores
- Primary database: **PostgreSQL** (one database per service).
- Cache and session store: **Redis**.
- Object storage: Amazon S3.

## Infrastructure
Everything runs on AWS in the **ap-south-1 (Mumbai)** region, on Kubernetes (EKS).
Deployments use a **blue-green** strategy to avoid downtime.

## Reliability
- The platform targets a **99.9% monthly uptime SLA**.
- Each service exposes a `/health` endpoint consumed by the load balancer.
- All inter-service calls carry a trace id for distributed tracing.

## Ownership
Every service has a named owning team recorded in the service catalogue, which also lists
the on-call rotation and runbook link.
