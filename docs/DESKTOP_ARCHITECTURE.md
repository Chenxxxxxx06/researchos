# ResearchOS Desktop Architecture

## 1. Objective

Deliver a signed, updateable desktop application without turning the current development stack into a hidden browser tab. Desktop and Web share product components and API contracts.

## 2. Selected shell

Tauri 2 is the target shell because ResearchOS benefits from low memory use, native file access, system credential storage, process supervision and small update payloads.

Electron remains a fallback prototype path only. It does not solve the current PostgreSQL, Redis, MinIO and Python startup cost.

## 3. Repository layout

```text
apps/
  web/       shared Next.js product interface
  api/       FastAPI domain services
  worker/    background Agent tasks
  desktop/   Tauri shell, capabilities and release configuration
```

## 4. Runtime modes

### Connected mode

The desktop shell loads the production ResearchOS Web application and connects to a configured API endpoint. This is the first releasable mode and requires no Docker installation on the user's machine.

### Local standalone mode

The desktop shell supervises packaged local services. This mode requires explicit adapters:

- PostgreSQL and pgvector to a desktop database and vector adapter
- Redis and Celery to a durable local queue adapter
- MinIO to a local artifact-store adapter
- FastAPI to a packaged Python sidecar
- Next development server to production assets or a standalone production server

The server deployment keeps PostgreSQL, Redis, Celery and S3-compatible storage. Desktop adapters must implement the same domain contracts rather than fork business logic.

## 5. Tauri responsibilities

- application window and native title bar integration
- single-instance behavior
- deep links
- native folder and file selection
- secure credential storage
- service readiness and restart UI
- local log collection
- updater and signed release manifests
- Windows MSI and NSIS bundles

Tauri does not access the research database directly. Product state continues through the API boundary.

## 6. Security boundary

- API keys and SSH secrets use the operating-system credential store
- external URLs open through an allowlisted shell capability
- local process commands are never exposed as a generic frontend invoke
- filesystem scope is restricted to user-approved workspaces
- updater signatures are mandatory before public release
- remote host-key verification remains mandatory

## 7. Release phases

1. Shared desktop detection and title-bar-safe Web shell
2. Tauri source scaffold and Windows bundle metadata
3. Connected-mode release with configurable API endpoint
4. Production Web and API startup optimization
5. Local storage, queue and database adapters
6. Packaged local sidecars
7. Signed installer, updater, crash recovery and release CI

## 8. Local build requirements

A full Tauri build requires Rust, Cargo, the Windows MSVC toolchain and WebView2. The source scaffold can be validated without Rust, but installer generation is blocked until those tools are installed on the build machine.
