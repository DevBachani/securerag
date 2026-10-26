# Planted Facts

Every checkable fact in the corpus and the document that holds it. This is the source of
truth for building the golden evaluation set in Phase 5. Keep it in sync when documents
change. `(PDF)` marks a fact that lives in a table inside a PDF.

> Note: this is **synthetic** data for a fictional company ("Acme Corp"). All names,
> numbers, emails and IDs are invented and do not describe any real person or organisation.

## public/ (allowed_groups: all)

### pub-leave-policy — Leave Policy
- Earned leaves per year: **24** (accrued 2/month).
- Max earned-leave carry-forward: **30 days**.
- Earned-leave encashment applies to balance above **15 days**.
- Casual leaves per year: **7**; sick leaves per year: **12**.
- Maternity leave: **26 weeks**; paternity leave: **10 working days**.
- Planned leave notice: **7 days** in advance.

### pub-holidays-2026 — Holiday Calendar 2026
- Fixed public holidays in 2026: **12**; optional/floating: **3**.
- Independence Day holiday date: **15 August 2026**.
- Diwali holiday date: **8 November 2026**.

### pub-travel-policy — Travel & Expense Policy v2.0
- Version **2.0**, effective **1 July 2026**.
- Domestic per diem: **INR 2,500/day**; international per diem: **USD 75/day**.
- Economy class required for flights under **6 hours**.
- Hotel cap: **INR 6,000/night** (metro), **INR 4,000/night** (non-metro).
- Flights must be booked **14 days** in advance; claims submitted within **30 days**.

### pub-code-of-conduct — Code of Conduct
- Gifts worth more than **INR 25,000** must be declined or reported.
- Whistleblower channel: **ethics@acme.example**.
- Dress code: **business casual**.

### pub-it-security — IT Security Basics
- Minimum password length: **14 characters**; MFA **mandatory**.
- Laptop auto-lock after **5 minutes**.
- Data classification levels: **4** (Public, Internal, Confidential, Restricted).
- Security incident reporting address: **secops@acme.example**.

### pub-office-locations — Office Locations
- Total employees: **~400**; office hours **09:30-18:30**.
- Bengaluru HQ capacity: **220 seats**; Pune: **90**; Hyderabad: **70**.

### pub-benefits — Benefits Overview
- Health insurance floater: **INR 5,00,000**; term life: **3x CTC**.
- Wellness allowance: **INR 15,000/year**; L&D budget: **INR 20,000/year**.
- Meal card: **INR 2,200/month**; ESOP eligibility after **1 year**.

### pub-onboarding — Onboarding Guide
- Probation period: **6 months**.
- Laptop provisioned within **2 working days**.
- IT helpdesk extension: **1800**.

## hr/ (allowed_groups: hr, leadership)

### hr-perf-review — Performance Review Process
- Review cycles per year: **2** (April and October).
- Rating scale: **1-5**; "5 - Outstanding" is top **~10%**.
- Promotion eligibility: rating **>= 4 for two consecutive cycles**.
- PIP trigger: rating **2 for two consecutive cycles** (60-day PIP).

### hr-hiring-plan — Hiring Plan FY27
- Headcount growth: **400 to 480** (net **+80**).
- By function: Engineering **50**, Sales **15**, G&A **15**.
- FY27 recruitment budget: **INR 28 crore**; avg cost-per-hire: **INR 1,20,000**.
- Agency fee cap: **8.33% of CTC**; campus drives: **3**.

### hr-salary-bands — Salary Bands FY27 (PDF)
- (PDF) L1 range: **6.0-9.0 LPA**; L3 midpoint: **18.0 LPA**.
- (PDF) L4 range: **22.0-34.0 LPA**; L7 maximum: **110.0 LPA**.

## hr/managers/ (allowed_groups: managers, hr, leadership)

### hr-manager-handbook — Manager Handbook
- Target span of control: **6-8 direct reports**.
- Weekly **1:1s** mandatory.
- Manager leave approval limit: **15 consecutive days**; expense approval: **INR 50,000**.

### hr-promotion-criteria — Promotion Criteria by Level
- Levels: **L1-L7**.
- L3 -> L4 requires **mentoring 2 juniors**.
- Promotion budget cap: **12% of team cost**; cycle **once a year in April**.

## finance/ (allowed_groups: finance, leadership)

### fin-vendor-contracts — Vendor Contracts Summary
- AWS annual spend: **INR 3.2 crore** (largest vendor).
- Microsoft: **INR 80 lakh**; Bengaluru HQ lease: **INR 1.1 crore**.
- Payment terms: **Net 45**; renewal notice: **60 days**.

### fin-q2-budget — Q2 FY27 Budget (PDF)
- (PDF) Total Q2 FY27 budget: **INR 36 crore**.
- (PDF) Engineering budget: **INR 18 crore** (50% of total); Sales: **INR 9 crore**.

### fin-expense-limits — Expense Approval Limits (PDF)
- (PDF) Employee limit: **INR 10,000**; Manager: **INR 50,000**.
- (PDF) Director: **INR 2,00,000**; VP: **INR 10,00,000**; CFO: **Unlimited**.

## engineering/ (allowed_groups: engineering)

### eng-architecture — Architecture Overview
- Number of microservices: **14**; event bus: **Kafka**.
- Databases: **PostgreSQL** + **Redis**; region: **AWS ap-south-1**.
- Uptime SLA target: **99.9%**; deploy strategy: **blue-green**.

### eng-oncall-runbook — On-Call Runbook
- Rotation tool: **PagerDuty**; rotation changes **weekly**.
- SEV1 response: **15 minutes**; SEV2 response: **1 hour**.
- Escalation after **30 minutes**; postmortem required within **48 hours**.

### eng-pm-payments — Postmortem ERR-4021
- Error code **ERR-4021**, date **14 January 2026**, duration **42 minutes**.
- Failed transactions: **~1,300**; root cause: **connection pool exhaustion**.
- Fix: pool size **20 -> 50**.

### eng-pm-auth — Postmortem ERR-5002
- Error code **ERR-5002**, date **8 March 2026**, duration **18 minutes**.
- Impact: **100% login failure**; root cause: **expired TLS certificate**.

### eng-pm-search — Postmortem ERR-6210
- Error code **ERR-6210**, date **22 June 2026**.
- p95 latency rose to **3.5 seconds**; **27%** of requests slow.
- Root cause: **missing database index**; fix: **composite index**.

### eng-deployment — Deployment Guide
- Deploy windows: **Tuesday and Thursday 14:00 IST**.
- Canary rollout: **5% -> 50% -> 100%**; rollback in **under 5 minutes**.

### eng-api-standards — API Standards
- API versioning starts at **/v1**; deprecation support **90 days**.
- Default rate limit: **100 requests/minute**; default page size **50**.
- Error code format: **ERR-XXXX**; auth: **Bearer JWT**.

## leadership/ (allowed_groups: leadership)

### lead-board-notes — Board Meeting Notes Q2 FY27
- Q2 FY27 revenue: **INR 62 crore** (up **18% YoY**); EBITDA margin **14%**.
- Cash runway: **22 months**; ESOP pool expanded to **8%**.
- Board seats: **7** (one independent seat open).

### lead-restructuring — Restructuring Plan (most sensitive)
- Consolidation: **6 business units -> 4 divisions**.
- Redundant roles: **18**; severance: **3 months' salary**.
- Employee communication timeline: **Q3 FY27**; effective **1 October 2026**.

### lead-ma-shortlist — M&A Target Shortlist
- Targets: **Nimbus Analytics (INR 45 crore)**, FinEdge Systems (INR 30 crore),
  QuantLeap AI (INR 22 crore).
- Max combined spend authorised: **INR 70 crore**; diligence begins **Q4 FY27**.
