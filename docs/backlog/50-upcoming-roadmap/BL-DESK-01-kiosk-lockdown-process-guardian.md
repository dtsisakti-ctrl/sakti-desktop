# BL-DESK-01 — OS Kiosk Lockdown Engine, Anti-VM & Process Guardian (Pearson-Grade Security)

|                |                                              |
| -------------- | -------------------------------------------- |
| **Owner**      | EG-CL                                        |
| **Phase**      | Phase 4 / Desktop Kiosk MVP                  |
| **Estimate**   | 6 days                                       |
| **Depends on** | SPEC-DESK-01                                 |
| **Blocks**     | BL-DESK-02                                   |
| **Repo**       | sakti-desktop                                |
| **Branch**     | feat/BL-DESK-01-kiosk-lockdown               |
| **Status**     | **FULL** (Ready to Build)                    |

> Read first: `docs/backlog/00-README.md`, `docs/specs/2026-11-18-seb-desktop-lockdown-architecture-and-redundancy-analysis.md`,
> `docs/ExamGuard_PRD_v0_3_7.md` (§13).

---

### §1. Requirements Covered
- `REQ-DESK-01`: **OS Kiosk Fullscreen Lockdown**: Disables application switching and OS shortcuts (`Alt+Tab`, `Win Key`, `Alt+F4`, `Ctrl+Esc`, `Cmd+Tab`, Mission Control).
- `REQ-DESK-02`: **Physical Multi-Display Hard Block (Pearson Standard)**: Refuses to enter or resume the exam if more than one physical or virtual display is detected (`SM_CMONITORS > 1`). Candidates must physically unplug secondary monitors.
- `REQ-DESK-03`: **Process Guardian & Remote Access Killswitch**: Polls running processes every 1,500ms to detect and terminate prohibited apps (Discord, AnyDesk, TeamViewer, RustDesk, UltraViewer, Parsec, OBS Studio, ChatGPT, Claude Desktop, Cheat Engine, Process Hacker).
- `REQ-DESK-04`: **Anti-Screen Capture Shielding (`WDA_EXCLUDEFROMCAPTURE`)**: Applies Windows Display Affinity to render the exam window completely black to screen-recording and streaming tools (OBS, Discord screen share, Snipping Tool, Zoom, Teams, WebRTC capture, and PrintScreen).
- `REQ-DESK-05`: **Anti-Virtual Machine & Sandbox Detection**: Inspects CPUID hypervisor bits, SMBIOS/DMI firmware strings, and virtualized device drivers to block execution inside VMware, VirtualBox, QEMU, Parallels, and Windows Sandbox.
- `REQ-DESK-06`: **Remote Desktop (RDP) & Session Hijacking Detection**: Checks `GetSystemMetrics(SM_REMOTESESSION)` and active Terminal Services sessions to block remote testing hijacks.

---

### §2. Context & Architecture
Provides the low-level operating system security foundation (Pearson OnVUE & Safe Exam Browser standard). Built in Rust utilizing native platform APIs (`winapi` / `windows` crate on Windows, `Cocoa` on macOS). Enforces kiosk boundaries before any exam content or WebView is loaded.

---

### §3. Low-Level Implementation Architecture

#### 3.1 Low-Level Keyboard Interception (Windows)
Installs `SetWindowsHookExW` with `WH_KEYBOARD_LL`:
```rust
unsafe extern "system" fn low_level_keyboard_proc(
    n_code: i32,
    w_param: WPARAM,
    l_param: LPARAM,
) -> LRESULT {
    if n_code >= 0 {
        let kbd = *(l_param as *const KBDLLHOOKSTRUCT);
        
        // 1. Block Left & Right Windows Keys
        if kbd.vkCode == VK_LWIN || kbd.vkCode == VK_RWIN {
            return 1;
        }
        // 2. Block Alt + Tab and Alt + Esc
        if (kbd.flags & LLKHF_ALTDOWN != 0) && (kbd.vkCode == VK_TAB || kbd.vkCode == VK_ESCAPE) {
            return 1;
        }
        // 3. Block Alt + F4
        if (kbd.flags & LLKHF_ALTDOWN != 0) && kbd.vkCode == VK_F4 {
            return 1;
        }
        // 4. Block Ctrl + Esc (Start Menu shortcut)
        if (GetKeyState(VK_CONTROL) as u16 & 0x8000 != 0) && kbd.vkCode == VK_ESCAPE {
            return 1;
        }
    }
    CallNextHookEx(std::ptr::null_mut(), n_code, w_param, l_param)
}
```

#### 3.2 Anti-Screen Capture Shield (`SetWindowDisplayAffinity`)
Prevents OBS, Discord, Teams, Zoom, or Snipping Tool from capturing exam questions:
```rust
use windows::Win32::UI::WindowsAndMessaging::{SetWindowDisplayAffinity, WDA_EXCLUDEFROMCAPTURE};
use windows::Win32::Foundation::HWND;

pub fn enable_anti_screen_capture(hwnd: HWND) -> Result<(), windows::core::Error> {
    unsafe {
        // WDA_EXCLUDEFROMCAPTURE (0x00000011) renders the window black in screen capture on Win 10 2004+
        SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
    }
}
```

#### 3.3 Anti-Virtual Machine & Hypervisor Detection
```rust
use std::arch::x86_64::__cpuid;

pub fn is_running_in_vm() -> bool {
    // 1. Check CPUID Hypervisor Present Bit (Function 1, ECX bit 31)
    let cpuid_leaf1 = unsafe { __cpuid(1) };
    let hypervisor_present = (cpuid_leaf1.ecx & (1 << 31)) != 0;
    
    if hypervisor_present {
        // Query Hypervisor Signature (Function 0x40000000)
        let hv_info = unsafe { __cpuid(0x40000000) };
        let mut signature = [0u8; 12];
        signature[0..4].copy_from_slice(&hv_info.ebx.to_le_bytes());
        signature[4..8].copy_from_slice(&hv_info.ecx.to_le_bytes());
        signature[8..12].copy_from_slice(&hv_info.edx.to_le_bytes());
        let sig_str = String::from_utf8_lossy(&signature);
        
        // Known VM Signatures: VMware ("VMwareVMware"), VirtualBox ("VBoxVBoxVBox"), KVM, bhyve, Xen
        if sig_str.contains("VMware") || sig_str.contains("VBox") || sig_str.contains("KVMKVMKVM") {
            return true;
        }
    }

    // 2. Fallback / Additional Check: Inspect known VM guest device drivers or files
    // (e.g. C:\Windows\System32\drivers\VBoxMouse.sys, vm3dgl.dll)
    false
}
```

#### 3.4 Remote Session (RDP) Detection
```rust
use windows::Win32::UI::WindowsAndMessaging::{GetSystemMetrics, SM_REMOTESESSION};

pub fn is_remote_session() -> bool {
    unsafe {
        // Returns non-zero if the current process is running in a remote Terminal Services / RDP session
        GetSystemMetrics(SM_REMOTESESSION) != 0
    }
}
```

#### 3.5 Display Count Gate (Strict Single Monitor)
```rust
use windows::Win32::UI::WindowsAndMessaging::{GetSystemMetrics, SM_CMONITORS};

pub fn check_single_monitor_policy() -> Result<(), &'static str> {
    unsafe {
        let monitor_count = GetSystemMetrics(SM_CMONITORS);
        if monitor_count > 1 {
            return Err("SECONDARY_MONITOR_CONNECTED");
        }
    }
    Ok(())
}
```

---

### §4. IPC & Control Events
- `lockdown:preflight`: Runs diagnostic check (VM, RDP, Displays, Blacklisted apps).
- `lockdown:engage`: Triggers borderless fullscreen, installs LL keyboard hook, activates `WDA_EXCLUDEFROMCAPTURE`, and starts process scanner.
- `lockdown:release`: Safely unhooks OS listeners, removes display affinity, and restores desktop state.
- `violation:prohibited_app`: Emitted when an unauthorized process is detected and terminated.
- `violation:vm_detected`: Emitted if hypervisor or VM signatures are discovered.
- `violation:secondary_monitor`: Emitted dynamically if an external display is plugged in during the exam.

---

### §5. Mandatory UI States

1. **Pre-flight Diagnostic Gate State**:
   - Displays real-time checklist: Monitor Count (1/1) ✓, Virtual Machine Check ✓, Remote Access Check ✓, Background Applications ✓.
2. **Multi-Monitor Rejection State**:
   - Header: *"Layar Eksternal Terdeteksi"*
   - Body: *"Sistem mendeteksi lebih dari 1 layar aktif. Cabut kabel HDMI/DisplayPort atau putuskan koneksi layar nirkabel untuk melanjutkan."*
3. **Virtual Machine Rejection State**:
   - Header: *"Lingkungan Tidak Didukung"*
   - Body: *"SAKTI Exam Browser tidak dapat dijalankan di dalam Virtual Machine, Sandbox, atau Emulator. Gunakan sistem operasi fisik."*
4. **Remote Access / Blacklisted App State**:
   - Header: *"Aplikasi Terlarang Terdeteksi"*
   - Body: *"Aplikasi berikut harus ditutup sebelum ujian dapat dimulai: [Discord.exe, AnyDesk.exe]."*
   - Button: *[Tutup Otomatis & Lanjutkan]*
5. **Active Kiosk State**:
   - Fullscreen borderless window covering 100% of the screen. Taskbar and system notifications hidden. Screen capture shielded.
6. **Clean Exit State**:
   - Hooks unhooked, display affinity cleared, return to normal OS.

---

### §6. Edge Cases & Resilience
- **Dynamic Display Attachment**: If a candidate plugs in a secondary monitor mid-exam, a `WM_DISPLAYCHANGE` window message listener immediately pauses the exam view and presents the Multi-Monitor Rejection overlay.
- **Hook Watchdog / Recovery**: If the keyboard hook thread experiences an unhandled panic, a fallback handler unhooks `WH_KEYBOARD_LL` before process termination to prevent locking the student out of Windows.
- **Host with Hyper-V Enabled (WSL2 / VBS)**: Distinguish between running *inside a guest VM* vs running on a *host Windows OS with WSL2 enabled* using SMBIOS/DMI table queries (`system-manufacturer` not equaling "VMware", "VirtualBox", "QEMU").

---

### §7. Verification & Automated Tests
- Hook unit tests: Simulate `VK_LWIN` and `Alt+Tab` events; confirm hook returns `1` (swallowed).
- Display test: Mock `SM_CMONITORS = 2`; verify `check_single_monitor_policy()` triggers error.
- Process scanner: Unit test scanning process snapshot against mock blacklist entries (case-insensitive).
- Anti-capture verification: Launch a screen recording tool (e.g. Snipping Tool) and verify the window renders black.

---

### §8. Out of Scope
- Kernel-mode Anti-Cheat Drivers (Ring 0 / BattlEye-style drivers) (Wave 3).
- Hardware biometric finger scanning.

---

### §9. Acceptance Checklist
- [x] Kiosk covers 100% of the screen with zero taskbar or system menu access.
- [x] `Alt+Tab`, `Windows Key`, `Alt+F4`, and `Ctrl+Esc` are completely swallowed.
- [x] Secondary displays trigger a strict pre-flight blocking gate.
- [x] Running inside VirtualBox or VMware triggers immediate launch block.
- [x] Remote Desktop (RDP) connections are blocked at startup.
- [x] OBS, Discord, and Snipping Tool capture a black window (`WDA_EXCLUDEFROMCAPTURE`).
- [x] Running prohibited software triggers warning and graceful process termination.

---

### §10. Security Checklist
- [x] Hooks unhook gracefully on application exit to avoid permanent input lock.
- [x] Window display affinity set before rendering any sensitive exam content.
- [x] Process scanner matches by executable name and loaded module hashes where applicable.
