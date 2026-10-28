# SnapLink

SnapLink is a Docker-based URL shortener with a browser interface for creating, sharing, and managing short links. It includes link analytics, optional aliases and expiry dates, browser-local link history, and backup/import tools for recovering links with their management tokens.

> **Project status:** This README documents the features and routes used in the current project context. Before deploying publicly, confirm the environment-variable names and startup commands against your own `.env.example`, `Dockerfile`, and `docker-compose.yml`.

## Features

- **Short links:** Convert a destination URL into a short URL.
- **Custom aliases:** Request a custom short code when creating a link, if enabled by the backend.
- **Expiry dates:** Optionally set a link expiry time.
- **Link analytics:** Retrieve click counts, creation time, last-click time, status, and expiry details.
- **Link management:** Disable an active short link using its management token.
- **Saved links:** Keep a convenient history in the current browser using `localStorage`.
- **TXT and JSON backups:** Download a human-readable `.txt` backup containing the short code and management token, or import a compatible SnapLink backup to restore a link.
- **Share and copy actions:** Share the short URL or copy it to the clipboard.
- **Docker-based local setup:** Run the application alongside its database and cache services using Docker Compose.

### Important notes about saved links and backups

- Saved-link history is stored in the browser that created or imported the link. It is not automatically synchronised between browsers or devices.
- Removing a link from browser history does **not** disable or delete the server-side link.
- Importing a backup verifies the code and management token with the backend. It does not recreate a link that has already been deleted from the server.
- A backup contains a management token. Treat it like a password: keep it private and do not commit it to source control or share it publicly.

## Technology

The project currently uses:

- HTML, CSS, and JavaScript for the web interface
- A Python-based API container
- PostgreSQL for persistent application data
- Redis for configured caching or supporting application services
- Docker and Docker Compose for local development
- Alembic for database migration versioning

The exact dependency versions and service names are defined by the project files.

## Project layout

The exact layout can vary by branch. The important files typically include:

```text
snaplink_production/
├── app/
│   └── static/
│       ├── index.html
│       ├── styles.css
│       └── app.js
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

Keep the backend source files and any migration directory already present in your repository. Do not replace your existing backend or migration files with this example layout.

## Requirements

Install the following before running SnapLink locally:

- Git
- Docker Desktop with Docker Compose
- A modern browser

On Windows, run the commands below in PowerShell from the project directory.

## Run locally

### 1. Get the project

If you have already cloned or downloaded the project, open a terminal in the project root. Otherwise, clone your repository first:

```powershell
git clone <YOUR_REPOSITORY_URL>
cd snaplink_production
```

Replace `<YOUR_REPOSITORY_URL>` with your repository URL and adjust the directory name if needed.

### 2. Create your local environment file

If `.env.example` exists, copy it to `.env`:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set the values required by the project. Use development-only secrets locally. **Do not commit `.env`.** The variable names in `.env.example` are the source of truth for this application; do not invent new variable names without updating the code/configuration that reads them.

If you do not have an `.env.example`, review `docker-compose.yml` and the backend configuration to determine which variables are required before starting the containers.

### 3. Build and start the services

```powershell
docker compose up --build -d
```

Check their status:

```powershell
docker compose ps
```

View recent logs if a service does not start:

```powershell
docker compose logs --tail=100
```

To inspect only the API logs, if the Compose service is named `api`:

```powershell
docker compose logs --tail=100 api
```

### 4. Open SnapLink

If your Compose configuration maps the API to port `8000`, open:

```text
http://localhost:8000/
```

If your configuration maps a different host port, use that port instead. After frontend changes, perform a hard refresh in the browser (`Ctrl+F5`) so cached JavaScript and CSS are reloaded.

### 5. Stop the services

```powershell
docker compose down
```

This stops the containers. Named database volumes normally remain in place. **Avoid `docker compose down -v` unless you deliberately want to delete the Compose-managed volumes and their stored data.**

## Basic usage

1. Open the SnapLink website.
2. Enter the destination URL.
3. Optionally enter a custom alias and expiry time if those controls are available.
4. Create the short link.
5. Save the management token securely.
6. Use Copy or Share to distribute the short URL.
7. Use View Analytics to refresh link statistics.
8. Download a TXT backup and store it somewhere private.
9. To restore a link in another browser, open the import section, choose the TXT or compatible JSON backup, and select **Verify and import link**.
10. Use Disable Link only when you intend to stop the server-side short link from redirecting.

## API examples

The examples below assume the API is reachable at `http://localhost:8000`.

### Create a short link (PowerShell)

```powershell
$body = @{ url = "https://www.wikipedia.org" } | ConvertTo-Json -Compress

$link = Invoke-RestMethod `
  -Uri "http://localhost:8000/api/v1/links" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body

$link
```

The response should include the short-link information and, when returned by the backend, a management token. Store the token securely; do not paste it into public logs or issue trackers.

### Get link analytics

The API route used by the frontend is:

```text
GET /api/v1/links/{code}/stats
```

The request must include the management token in the `X-Management-Token` header. Example:

```powershell
$code = "YOUR_SHORT_CODE"
$token = "YOUR_MANAGEMENT_TOKEN"

Invoke-RestMethod `
  -Uri "http://localhost:8000/api/v1/links/$code/stats" `
  -Headers @{ "X-Management-Token" = $token }
```

Replace the example values with your actual code and token. Never publish a real management token.

### Disable a link

The frontend uses this route to disable a link:

```text
DELETE /api/v1/links/{code}
```

It sends the management token through the `X-Management-Token` header. Test disabling only with a disposable link because the action affects the server-side link.

## Database and migrations

The project has used PostgreSQL tables such as `short_links`, `abuse_reports`, and `alembic_version`. Your current migrations determine the actual schema.

- Keep PostgreSQL data in a persistent volume locally and a managed persistent database in production.
- Apply migrations using the migration command configured by the project (commonly `alembic upgrade head` for Alembic projects); verify the correct working directory and database URL before running it.
- Do not manually drop tables or remove database volumes as a routine troubleshooting step.
- Take a backup before making schema changes or running destructive SQL.

## Preparing for production deployment

A possible hosting setup is a Docker-capable application platform with managed PostgreSQL and Redis. Railway is one option, but the production service configuration must match this repository.

### Before deploying

- [ ] Confirm that the application starts successfully with Docker Compose locally.
- [ ] Confirm which environment variables the backend actually reads by reviewing `.env.example`, `docker-compose.yml`, and backend settings.
- [ ] Ensure the web server binds to `0.0.0.0` and uses the port required by the hosting platform (often provided through a `PORT` environment variable).
- [ ] Use managed PostgreSQL and Redis services for production rather than relying on a local development database container.
- [ ] Configure production database and Redis connection strings using the platform's private variables or service-reference mechanism.
- [ ] Make sure database migrations run before the application depends on the new schema.
- [ ] Keep `.env`, management tokens, secret keys, and production credentials out of Git.
- [ ] Configure HTTPS and verify redirects use the deployed public hostname.
- [ ] Test create, redirect, analytics, disable, TXT backup, and import against the deployed site.
- [ ] Add abuse prevention and rate limiting before inviting the public to use the URL shortener.

### Push code to GitHub safely

Before committing, review the staged files:

```powershell
git status
```

If needed, add these patterns to `.gitignore`:

```gitignore
.env
.env.*
!.env.example
__pycache__/
*.py[cod]
.venv/
venv/
.pytest_cache/
*.log
```

Then commit and push using your repository's configured remote. Check that no real credentials, backup TXT files, database dumps, or private tokens are included.

### Official deployment references

- [Railway documentation](https://docs.railway.com/)
- [Railway PostgreSQL](https://docs.railway.com/databases/postgresql)
- [Railway Redis](https://docs.railway.com/databases/redis)
- [Railway Docker deployment guide](https://docs.railway.com/guides/dockerfiles)

Hosting requirements and pricing can change; confirm the current platform documentation before deployment.

## Troubleshooting

### Docker cannot download the base image

If the build reports a DNS error such as `lookup registry-1.docker.io: no such host`, this is usually a Docker/network/DNS issue rather than a frontend code error.

Try:

```powershell
nslookup registry-1.docker.io
nslookup google.com
```

If name resolution fails, restart Docker Desktop and, if necessary, restart WSL from PowerShell:

```powershell
wsl --shutdown
```

Then reopen Docker Desktop and retry the build. Do not delete database volumes to troubleshoot a DNS issue.

### A container exits or restarts

```powershell
docker compose ps
docker compose logs --tail=100
```

Look for missing environment variables, database connection failures, migration errors, or incorrect start commands.

### The website loads but a feature fails

1. Hard-refresh the page with `Ctrl+F5`.
2. Check the API container logs.
3. Open the browser developer tools and inspect the Console and Network tabs.
4. Confirm that the frontend endpoint, database URL, and management-token header match the backend routes.

### TXT backup import fails

- Make sure the selected file is a SnapLink backup, not an unrelated text file.
- Do not remove the `--- IMPORT DATA (keep intact) ---` marker or t
he JSON data below it from a TXT backup.
- Confirm the short code and management token still refer to a link that exists on the server.
- Remember that importing verifies an existing link; it does not recreate a server-side link that has been deleted.



