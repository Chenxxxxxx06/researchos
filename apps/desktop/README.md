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
