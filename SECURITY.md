# Security

## Reporting a vulnerability

Please do not open a public issue for a security problem. Contact the repository maintainers privately and include:

- what is affected (API, UI, storage, auth)
- how to reproduce it
- the impact you expect

If this repository is on GitHub, use **Security → Report a vulnerability** (private vulnerability reporting) when that feature is enabled.

## Secrets

Runtime credentials are environment variables, not files in git. Never commit:

- `RCA_API_KEYS`, `RCA_JWT_SECRET`, `RCA_ADMIN_TOKEN`
- `RCA_S3_ACCESS_KEY_ID`, `RCA_S3_SECRET_ACCESS_KEY`, or `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`
- `.env` files, cloud credential files, or private keys

`.env.example` lists the variable names with empty secret fields. The Postgres user and password in `backend/docker-compose.postgres.yml` (`rca` / `rca`) are for the local Docker database only. Use a real secret store and a strong password for any shared or production database.

## Auth defaults

If `RCA_API_KEYS` and `RCA_JWT_SECRET` are both empty, the API trusts the `X-Tenant-ID` header. That mode is for local development. Set API keys or JWT verification before exposing the API beyond your machine.
