# API Standards

**Owner:** Engineering · **Sensitivity:** Internal · **Audience:** Engineering

## Style
All public APIs are **REST over HTTPS** with JSON payloads. Resources are plural nouns
(`/invoices`, `/users`).

## Versioning
APIs are versioned in the path, starting at **`/v1`**. Breaking changes require a new major
version. A deprecated version is supported for **90 days** after its replacement ships.

## Limits and pagination
- Default **rate limit: 100 requests per minute** per client, returned in `X-RateLimit-*`
  headers.
- List endpoints paginate with a **default page size of 50** and a maximum of 200.

## Errors
Errors use a consistent envelope with a machine-readable code in the format **`ERR-XXXX`**
(for example `ERR-4021`) and an HTTP status that matches the failure class.

## Authentication
Clients authenticate with a **Bearer JWT** in the `Authorization` header. Tokens expire
after 60 minutes and must be refreshed.
