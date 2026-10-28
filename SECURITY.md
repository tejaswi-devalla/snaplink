# Security policy

SnapLink is a portfolio project and has not been independently audited. Do not assume it is suitable for high-risk or high-volume public use without an additional security review.

## Before public launch

- Configure HTTPS, `DATABASE_URL`, TLS-enabled/private `REDIS_URL`, `PUBLIC_BASE_URL`, `ADMIN_API_KEY`, backups, and the correct trusted reverse-proxy ranges.
- Replace every sample secret and keep `.env` outside source control.
- Add provider-level DDoS protections, alerting, dependency scanning, and a tested recovery process.
- Establish an abuse-report triage and takedown contact. The app stores reports and exposes a protected moderation API, but it does not automatically scan destinations.
- Review privacy, retention, acceptable-use, and disclosure requirements for your users and jurisdiction.

## Reporting a vulnerability

Before publishing this repository, configure a security contact in your repository's GitHub Security settings or in a project security policy. Do not promise a response time until an owner can support it. Please avoid publishing secrets, live management tokens, database connection strings, or reproduction details that would put active users at risk.
