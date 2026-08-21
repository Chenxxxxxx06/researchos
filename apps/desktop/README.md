# ResearchOS Desktop

Tauri 2 shell for ResearchOS. The first release mode connects to an existing local or hosted ResearchOS Web endpoint. The bootstrap screen automatically probes the last endpoint and opens the full workspace when it is ready.

## Validate source

```bash
pnpm --filter researchos-desktop validate
```

## Build prerequisites on Windows

- Rust stable and Cargo
- Visual Studio Build Tools with Desktop development with C++
- WebView2 Runtime
- Node.js and pnpm

Then run:

```bash
pnpm --filter researchos-desktop build
```

The current machine must have the Rust toolchain before Tauri can generate MSI or NSIS installers. Product architecture and local-standalone migration are documented in `docs/DESKTOP_ARCHITECTURE.md`.

## Windows release artifacts

A release build produces three ways to try the app:

- `researchos-desktop.exe` — portable application; no installer required
- `bundle/nsis/ResearchOS_<version>_x64-setup.exe` — recommended Windows installer
- `bundle/msi/ResearchOS_<version>_x64_en-US.msi` — MSI package for managed deployment

This release is the connected desktop mode: start a local ResearchOS site or provide a hosted HTTPS endpoint, open the app, verify that the workspace is ready, and select **连接**. The WebView2 Runtime is required on Windows. Tagged releases publish all three binaries and their SHA-256 checksums to GitHub Releases.
