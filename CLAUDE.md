You are an expert at creating API's with RESTful Principles in Python.

## Environment

- You are encouraged to use Chrome, documentation, and any AI tools to assist development.
- You have passwordless sudo access to install additional dependencies via apt or brew.
- Pre-installed utilities: GitHub CLI (gh), doctl, s3cmd, jq, yq, neovim, and core image processing libraries.

## Project Objective

Build a production-ready REST API service that accepts a long URL, generates a shortened URL (alias), redirects users to the original URL, and returns metadata about the created short links.

## Functional Expectations

- **Creation:** Accept a long URL and always generate a new unique shortened URL. If the same long URL has been shortened before, a new alias is created — do not return the existing one.
- **Customization:** Support either automatically generated short codes or user-defined custom aliases (with appropriate validation).
- **Redirection:** Redirect users to the original URL when the shortened link is accessed.
- **Metadata & Retrieval:** Return metadata about the shortened URL and allow the retrieval of metadata for an existing short URL.

## Engineering Expectations

- **Architecture Flow Diagram:** Include a diagram in your repository mapping the request lifecycle and data flow at a high level. This will serve as the anchor for your technical review.
- **Validation:** Sensible error handling, input validation, and edge-case management.
- **Testing:** Unit or integration tests that demonstrate correctness.
- **CI/CD:** A basic pipeline configuration (e.g., GitHub Actions).
- **Documentation:** A well-organized codebase and a README providing clear setup, execution, and testing instructions.

## Tech Stack

- **Framework:** FastAPI (Python) — async-native, automatic OpenAPI docs
- **Database:** PostgreSQL — persistent storage for links and metadata
- **Cache:** Redis — fast alias lookups and redirect caching
- **Task Queue:** Celery + Redis broker — background jobs (e.g., click tracking, cleanup)
- **Migrations:** Alembic — PostgreSQL schema version control
- **Rate Limiting:** `slowapi` with a Fixed Window algorithm — abuse prevention on creation and redirect endpoints
- **Authentication:** `python-jose` for JWT signing/verification, `passlib[bcrypt]` for password hashing
- **Authorization:** RBAC enforced via FastAPI dependencies
- **Testing:** pytest — unit and integration tests
- **Logging:** Python `logging` with structured output (JSON-formatted for production)

## API Routes

All management endpoints are versioned under `/api/v1`. The redirect endpoint lives at the root for clean, short URLs.

### Tokens (Auth)

| Method | Path               | Description                                       | Access        |
|--------|--------------------|---------------------------------------------------|---------------|
| POST   | `/api/v1/tokens`   | Login — issue access + refresh JWT tokens         | Public        |
| PUT    | `/api/v1/tokens`   | Exchange a refresh token for a new access token   | Authenticated |
| DELETE | `/api/v1/tokens`   | Logout — invalidate the refresh token             | Authenticated |

### Users

| Method | Path                  | Description                            | Access        |
|--------|-----------------------|----------------------------------------|---------------|
| POST   | `/api/v1/users`       | Register a new user account            | Public        |
| GET    | `/api/v1/users`       | List all users (paginated)             | Admin only    |
| GET    | `/api/v1/users/:id`   | Get a specific user's details          | Admin only    |
| DELETE | `/api/v1/users/:id`   | Delete a user and all their links      | Admin only    |

### Redirect (Core)

| Method | Path      | Description                            |
|--------|-----------|----------------------------------------|
| GET    | `/:alias` | Redirect to the original URL (302/301) |

### Links Resource

| Method | Path                     | Description                                         |
|--------|--------------------------|-----------------------------------------------------|
| POST   | `/api/v1/links`          | Create a new shortened URL                          |
| GET    | `/api/v1/links`          | List all short links (paginated)                    |
| GET    | `/api/v1/links/:alias`   | Get metadata for a specific short link              |
| PUT    | `/api/v1/links/:alias`   | Update a short link (destination URL, expiry, etc.) |
| DELETE | `/api/v1/links/:alias`   | Delete a short link                                 |

### Analytics

| Method | Path                          | Description                            |
|--------|-------------------------------|----------------------------------------|
| GET    | `/api/v1/links/:alias/stats`  | Get click/access statistics for a link |

### Health

| Method | Path             | Description          |
|--------|------------------|----------------------|
| GET    | `/api/v1/health` | Service health check |

## Authentication & Authorization

### Authentication — JWT

- On login (`POST /api/v1/tokens`), issue a short-lived **access token** (e.g., 15 min) and a long-lived **refresh token** (e.g., 7 days).
- Clients pass the access token as a `Bearer` token in the `Authorization` header on protected routes.
- On expiry, clients use `PUT /api/v1/tokens` with their refresh token to obtain a new access token without re-logging in.
- Refresh tokens are stored in PostgreSQL and invalidated on logout or user deletion.
- Use `python-jose` for signing/verifying JWTs and `passlib[bcrypt]` for password hashing.

### Authorization — RBAC

Two roles:

| Role    | Permissions                                                          |
|---------|----------------------------------------------------------------------|
| `user`  | Create, read, update, and delete their own links only                |
| `admin` | Full access — manage all links, list/delete any user, view all stats |

- Role is stored on the user record in PostgreSQL and embedded in the JWT payload as a claim.
- FastAPI dependencies enforce role checks on each protected route before the handler runs.

### Response Status Codes & Information Disclosure

Responses must not reveal information that could aid enumeration or credential stuffing:

| Scenario                                          | Status | Notes                                                                 |
|---------------------------------------------------|--------|-----------------------------------------------------------------------|
| Successful resource creation                      | `201`  |                                                                       |
| Successful read / update                          | `200`  |                                                                       |
| Successful delete                                 | `204`  | No body                                                               |
| Login failure (wrong password **or** no account) | `401`  | Always the same message — never distinguish the two cases             |
| Missing or invalid token                          | `401`  | Include `WWW-Authenticate: Bearer` header                             |
| Expired token                                     | `401`  | Same response as invalid token — do not leak expiry detail            |
| Authenticated but wrong role                      | `403`  |                                                                       |
| Accessing another user's link                     | `404`  | Return Not Found rather than Forbidden to avoid resource enumeration  |
| Validation / bad input                            | `422`  |                                                                       |
| Rate limit exceeded                               | `429`  | Include `Retry-After` header                                          |

## Rate Limiting

Use `slowapi` (built on `limits`) with a **Fixed Window** algorithm backed by Redis.

- Fixed Window resets the counter at the start of each time window (e.g., 100 requests per minute per IP). Simple to reason about and sufficient for Stage 1.
- Apply limits to the creation endpoint (`POST /api/v1/links`) and the redirect endpoint (`GET /:alias`) as the two highest-traffic and most abuse-prone routes.
- Return `429 Too Many Requests` with a `Retry-After` header when the limit is exceeded.

## Testing Strategy

- **Unit Tests:** Test individual service functions, alias generation, validation logic, and utilities in isolation (mocked dependencies).
- **Integration Tests:** Test full request/response cycles against a real PostgreSQL and Redis instance (via pytest fixtures / testcontainers).
- **Coverage:** Aim for high coverage on core business logic (creation, redirection, metadata retrieval).

## Logging

- Use Python's `logging` module with a JSON formatter for structured, machine-readable logs in production.
- Log key lifecycle events: link creation, redirects, cache hits/misses, validation errors, and background task outcomes.
- Include request IDs in log context for traceability across a request's lifecycle.

## Extensions & Next Steps

If time permits, expand on your solution:

- **Deployment:** Deploy your service to DigitalOcean.
- **Customer-Centric Features:** Add additional features you would expect a product like this to have, using your imagination and thinking from a customer's perspective.
