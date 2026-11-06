# `nio-limb` — Referenz-Implementierung einer NIO Rust-Limb als cdylib

Diese Crate kompiliert zu einer Shared Library (`libnio_limb.so` unter Linux)
und exportiert die stabile C-FFI, die der Python-Orchestrator in
`orchestrator/kanban/limb_ffi.py` lädt:

| Symbol | Signatur | Aufgabe |
|--------|----------|---------|
| `limb_contract_version` | `() -> *const c_char` | Contract-Version ("1.0"), wird beim Laden geprüft |
| `init_limb` | `() -> c_int` | Einmalige Initialisierung (0 = Erfolg) |
| `process_payload` | `(data, data_len, out, out_cap, out_len) -> c_int` | High-Speed-Payload-Verarbeitung auf Pointern |
| `shutdown_limb` | `(void)` | Ressourcen freigeben vor `dlclose` |

## Build

Benötigt den Rust-Toolchain (nicht in dieser Sandbox installiert, deshalb hier
Quelle nur; der `make check`-Tor überspringt Rust ohne `cargo`):

```bash
cargo build --release --manifest-path rust/nio-limb/Cargo.toml
# -> rust/nio-limb/target/release/libnio_limb.so
```

Der Ordner `rust/nio-limb/target/` gehört nicht ins Git (siehe
`.gitignore`). Fertige `.so`-Artefakte werden aus dem Vault/Refinement-Pipeline
angetragen, nie aus dem Repository gebaut.

## Vertrag mit Python

`orchestrator/kanban/limb_ffi.py::LimbHotReloader` lädt die `.so` via `ctypes`,
prüft die Contract-Version, ruft `init_limb` und tauscht bei `reload()` atomar
aus: neue Bibliothek laden + initialisieren **vor** `dlclose` der alten. Ein
defektes Ersatzartefakt lässt die laufende Limb unangetastet.
