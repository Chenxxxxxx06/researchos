# ResearchOS — Phase 1 Architecture Decisions

Status: **Accepted** (confirmed before coding).
Scope: Phase 1 — Auth + Organizations + Projects + Project Workspace shell.
Builds on `docs/PHASE0_DECISIONS.md`.

---

## 1. Decision Log

| # | Topic | Decision | Rationale / Notes |
|---|-------|----------|-------------------|
| P1-D1 | Tenant model | Introduce **`organization_memberships`** (user ↔ organization, M:N, with an org-level role). | Refines the docs ERD (which drew org→users 1:N but defined no FK). Supports teams/multi-org from the start. |
| P1-D2 | Sessions | **Redis server-side sessions** with an opaque token in an HttpOnly cookie (`ros_session`). No JWT. | Revocable, no PII in the cookie, supports logout-all later. An optional `sessions` audit table is deferred. |
| P1-D3 | CSRF | **Double-submit token, signed with itsdangerous and bound to the session id.** Cookie `ros_csrf` is readable by JS; the same value must be echoed in the `X-CSRF-Token` header on every POST/PUT/PATCH/DELETE. | Not a bare random value: the token is `signer.sign(session_id)` and is verified by signature + binding + max-age. |
| P1-D4 | Password hashing | **argon2id** via `pwdlib[argon2]`. | Modern, recommended default. |
| P1-D5 | Permission resolution | Effective project role = explicit `project_membership` role, OR implicit `admin` if the actor is `owner`/`admin` of the project's organization. Enforced in the **service layer**. | Role ladders: org `member < admin < owner`; project `viewer < researcher < admin < owner`. |
| P1-D6 | Resource visibility | No visibility → **404** (hides existence, also enforces tenant isolation). Visible but insufficient role → **403**. | Prevents resource enumeration across tenants. |
| P1-D7 | Project deletion | **Soft delete** — `DELETE /projects/{id}` sets `status = archived`. No physical deletion. | Reversible and safe. |
| P1-D8 | Cookie security | `Secure` is environment-driven: `false` for local HTTP dev, **`true` in production**. `HttpOnly=true` for the session cookie; `SameSite=Lax` for both. | See `Settings.session_cookie_secure`. |
| P1-D9 | Login failures | Always return **401 "invalid credentials"** — never reveal whether the email exists. | Anti-enumeration. |
| P1-D10 | Primary keys / UUIDs | UUID PKs generated **application-side** (`uuid4`), not `gen_random_uuid()`. | Avoids a hard dependency on the `pgcrypto` extension; DB-portable. |
| P1-D11 | Enums | Use **PostgreSQL native enums** (`org_role`, `project_role`, `project_status`). | See migration risk below. |
| P1-D12 | Frontend form validation | Add **zod** for client-side form schemas. | Immediate, typed client-side validation that complements (never replaces) server-side validation. |

## 2. New dependencies

Backend (`apps/api`): `pwdlib[argon2]`, `email-validator` (for Pydantic `EmailStr`), `itsdangerous`.
Frontend (`apps/web`): `zod`, plus shadcn-style primitives and Radix peers they require.

## 3. Native enum migration risk (P1-D11)

PostgreSQL native enums are convenient but **adding or renaming values later requires
`ALTER TYPE ... ADD VALUE`** (which cannot run inside a transaction prior to PG12 and
still has ordering constraints), and **removing a value is not supported** without
recreating the type. Mitigation / exit path if this becomes painful:

1. Create a new `text` column with a `CHECK` constraint mirroring the allowed values.
2. Backfill from the enum column.
3. Drop the enum column and `DROP TYPE`.

Each enum here is referenced by exactly one table (`org_role` → memberships,
`project_role` → project memberships, `project_status` → projects), which keeps any
future migration localized.

## 3a. Implementation addenda (added during build)

- **Org member management endpoint.** `POST /organizations/{org_id}/members`
  (org admin+) was added so existing users can be added to an organization.
  Without it, project membership (which requires the target to already belong to
  the org) would be unreachable. This is within the Organizations scope.
- **`DB_USE_NULLPOOL` setting.** A non-pooling engine option. Enabled for the
  test suite because each test runs in its own event loop and a pooled
  connection must not outlive the loop that created it.
- **Tests run inside the compose network.** The Windows host has a local
  PostgreSQL occupying port 5432, so the host cannot reach the Docker Postgres.
  The suite runs via `docker-compose.test.yml` against the `postgres`/`redis`
  service hostnames (the in-container path proven by `/readyz`).

## 4. Phase 1 explicit non-goals

No Research Copilot, AI agent runtime, experiments, LaTeX, skills runtime, WebSocket
business events, memory graph, or remote SSH. The project overview page renders
empty "coming soon" placeholders for those future modules.
