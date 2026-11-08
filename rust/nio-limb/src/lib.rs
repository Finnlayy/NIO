//! NIO Rust-Limb — baubar als Shared Library (cdylib).
//!
//! Die Bibliothek exportiert eine stabile, C-kompatible FFI, die der
//! Python-Orchestrator zur Laufzeit via ctypes laden und austauschen kann:
//!
//!     int   init_limb(void);
//!     int   process_payload(const uint8_t *data, size_t data_len,
//!                           uint8_t *out, size_t out_cap, size_t *out_len);
//!     void  shutdown_limb(void);
//!     const char *limb_contract_version(void);
//!
//! Build:
//!     cargo build --release --manifest-path rust/nio-limb/Cargo.toml
//! Artefakt: rust/nio-limb/target/release/libnio_limb.so
//!
//! Der Vertrag (Contract Version "1.0") ist auf Python-Seite in
//! orchestrator/kanban/limb_ffi.py kodiert und wird bei jedem Laden geprueft.

use std::ptr::copy_nonoverlapping;

/// FFI-Vertrags-Version. Muss mit `_CONTRACT_VERSION` in
/// `orchestrator/kanban/limb_ffi.py` identisch sein.
pub const LIMB_CONTRACT_VERSION: &str = "1.0";

/// Groesstes erlaubtes Ausgabepaket pro Aufruf (Schutz gegen zu grosse
/// Caller-Buffer auf der Python-Seite).
const MAX_OUT: usize = 65536;

#[no_mangle]
pub extern "C" fn limb_contract_version() -> *const std::os::raw::c_char {
    LIMB_CONTRACT_VERSION.as_ptr() as *const std::os::raw::c_char
}

/// Einmalige Initialisierung der Limb (z. B. interne Zustandsmaschine).
/// Liefert 0 bei Erfolg, sonst Fehler-Code < 0.
#[no_mangle]
pub extern "C" fn init_limb() -> std::os::raw::c_int {
    0
}

/// Verarbeitet ein Payload direkt auf dem Pointer (High-Speed-Pfad, kein
/// Kopieren zwischen Prozessen ausser den Shared-Memory-Ring).
///
/// `data`/`data_len` beschreiben den Eingabe-Puffer, `out`/`out_cap` den
/// Caller-Ausgabepuffer; `out_len` recibe die tatsaechliche Ausgabe-Groesse.
/// Rueckgabe: 0 = Erfolg, < 0 = Fehler-Code.
#[no_mangle]
pub extern "C" fn process_payload(
    data: *const u8,
    data_len: usize,
    out: *mut u8,
    out_cap: usize,
    out_len: *mut usize,
) -> std::os::raw::c_int {
    if data.is_null() || out.is_null() || out_len.is_null() {
        return -1; // E_INVAL
    }
    if data_len > MAX_OUT {
        return -2; // E_TOO_BIG
    }

    let input = unsafe { std::slice::from_raw_parts(data, data_len) };

    // Beispiel-Logik: NIO-Praefix + Rohdaten als Ausgabepaket.
    let mut packet = Vec::with_capacity(input.len() + 4);
    packet.extend_from_slice(b"NIO");
    packet.extend_from_slice(input);

    if packet.len() > out_cap {
        return -3; // E_OUT_BUFFER_TOO_SMALL
    }

    unsafe {
        copy_nonoverlapping(packet.as_ptr(), out, packet.len());
        *out_len = packet.len();
    }
    0
}

/// Freigabe aller Ressourcen der Limb vor dem Entladen der Bibliothek.
#[no_mangle]
pub extern "C" fn shutdown_limb() {
    // Keine allokierten Ressourcen in dieser Referenz-Implementierung.
}
