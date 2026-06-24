# ResearchOS Security Design

## 1. Security Principles

- Treat remote code, LaTeX projects, third-party skills, and uploaded PDFs as untrusted.
- Enforce tenant isolation in every domain service.
- Agents inherit user permissions and skill policy restrictions.
- Secrets are never exposed to agents or stored in logs.
- Risky actions require explicit approval.

## 2. Authentication

MVP:

- Email/password or OAuth.
- Secure HTTP-only cookies.
- CSRF protection for browser session flows.
- Optional API keys for ingestion or CLI integrations.

Later:

- SSO/SAML.
- SCIM provisioning.
- Enterprise audit exports.

## 3. Authorization

Roles:

- Owner
- Admin
- Researcher
- Viewer

Permission dimensions:

- Organization
- Project
- Resource
- Tool
- Skill
- Runtime profile

## 4. Agent Security

Controls:

- Tool allowlists
- Approval gates
- Tool-call audit logs
- Prompt injection defenses for retrieved content
- Source attribution
- Output validation
- Secrets redaction

Agents must not:

- Access credentials directly.
- Execute remote commands without policy approval.
- Install skills without permission.
- Write paper claims without source or assumption markers.

## 5. Skill Security

Third-party skills require:

- Manifest validation
- Signed packages
- Permission declarations
- Static scanning
- Version pinning
- Revocation
- Sandbox execution
- Network and filesystem restrictions

MVP should only allow first-party executable skill logic.

## 6. Runtime Security

SSH:

- Encrypt credentials.
- Scope runtime profiles by organization/project.
- Redact command logs.
- Record approvals.
- Support cancellation and timeouts.

LaTeX:

- Container isolation.
- Shell escape disabled by default.
- CPU/memory/time limits.
- No network by default.

File processing:

- File size limits.
- MIME validation.
- Virus scanning where available.
- Safe PDF parsing workers.

## 7. Data Protection

- Encrypt data at rest where managed services support it.
- Use TLS everywhere.
- Separate production and staging secrets.
- Implement deletion workflows for projects and organizations.
- Support export of project data.

## 8. Audit Logs

Audit:

- Login events
- Project membership changes
- Skill installs
- Agent tool calls
- Remote command launches
- Credential changes
- Paper/document export
- Permission changes

## 9. Abuse and Cost Controls

- Rate limits by user, project, and organization.
- LLM spend quotas.
- Queue limits.
- Remote runtime concurrency limits.
- Marketplace moderation.
- Admin kill switch for unsafe skills.
