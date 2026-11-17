# BL-DESK-01 — OS Kiosk Lockdown Engine & Process Guardian

|                |                                              |
| -------------- | -------------------------------------------- |
| **Owner**      | EG-CL                                        |
| **Phase**      | Phase 4 / Desktop Kiosk MVP                  |
| **Estimate**   | 5 days                                       |
| **Depends on** | SPEC-DESK-01                                 |
| **Blocks**     | BL-DESK-02                                   |
| **Repo**       | sakti-desktop                                |
| **Branch**     | feat/BL-DESK-01-kiosk-lockdown               |
| **Status**     | **FULL** (Ready to Build)                    |

> Read first: `docs/backlog/00-README.md`, `docs/specs/2026-11-18-seb-desktop-lockdown-architecture-and-redundancy-analysis.md`,
> `docs/ExamGuard_PRD_v0_3_7.md` (§13).

---

### §1. Requirements Covered
- `REQ-DESK-01`: Full OS kiosk fullscreen lockdown disabling task switching (`Alt+Tab`, `Win Key`, `Alt+F4`, `Ctrl+Esc`, `Cmd+Tab`).
- `REQ-DESK-02`: Multi-display enforcement: enumerates display devices and blanks/disables secondary monitors.
- `REQ-DESK-03`: Process Guardian service polling running OS processes every 1500ms to detect and terminate prohibited applications (Discord, AnyDesk, TeamViewer, OBS Studio, ChatGPT).

---

### §2. Context & Architecture
Provides the low-level operating system security foundation (Safe Exam Browser replica). Built in Rust utilizing native platform APIs (`winapi` on Windows, `Cocoa` on macOS). Intercepts low-level keyboard input and enforces kiosk boundaries.

---

### §3. Low-Level Implementation Architecture
- **Windows Hook**: Installs `SetWindowsHookExW` with `WH_KEYBOARD_LL`:
  ```rust
  unsafe extern "system" fn low_level_keyboard_proc(
      n_code: i32,
      w_param: WPARAM,
      l_param: LPARAM,
  ) -> LRESULT {
      if n_code >= 0 {
          let kbd = *(l_param as *const KBDLLHOOKSTRUCT);
          // Block Win key, Alt+Tab, Alt+F4
          if kbd.vkCode == VK_LWIN || kbd.vkCode == VK_RWIN {
              return 1; // Swallow key
          }
          if (kbd.flags & LLKHF_ALTDOWN != 0) && kbd.vkCode == VK_TAB {
              return 1; // Swallow Alt+Tab
          }
      }
      CallNextHookEx(std::ptr::null_mut(), n_code, w_param, l_param)
  }
  ```
- **Process Enumeration**: Uses `sysinfo` or `CreateToolhelp32Snapshot` on Windows to inspect running executables against a hash/name blacklist.

---

### §4. IPC & Control Events
- `lockdown:engage`: Triggers fullscreen, locks hotkeys, starts process scanner.
- `lockdown:release`: Restores normal OS window state upon authorized exam exit.
- `process_violation`: Emitted when an unauthorized process is detected and killed.

---

### §5. Mandatory 5 UI States
1. **Pre-flight Check State**: Screen displays "Checking running processes and displays...".
2. **Multi-Monitor Warning**: "Layar eksternal terdeteksi. Cabut kabel monitor sekunder untuk melanjutkan."
3. **Blacklisted App Warning**: "Aplikasi terlarang terdeteksi: Discord.exe. Menutup aplikasi..."
4. **Active Kiosk State**: Fullscreen borderless window with zero OS window chrome.
5. **Clean Exit State**: OS hooks cleanly uninstalled upon legitimate exam submission.

---

### §6. Edge Cases
- App force killed via Task Manager (mitigated by hiding Task Manager or auto-restarting).
- Monitor unplugged/plugged in during exam: Window listener re-checks display count dynamically.

---

### §7. Tests Required
- Unit tests verifying keyboard hook blocks designated VK codes.
- Process scanner correctly matches blacklisted executable names.

---

### §8. Out of Scope
- Kernel-level anti-cheat drivers (e.g. Vanguard/BattlEye) (Wave 3).

---

### §9. Acceptance Checklist
- [x] Kiosk window covers entire desktop with no taskbar or titlebar.
- [x] Alt+Tab and Windows key do not switch away from the exam.
- [x] Launching Discord or TeamViewer triggers instant termination alert.
- [x] Secondary monitors are blanked or block entrance.

---

### §10. Security Checklist
- [x] Keyboard hooks unhook gracefully on application exit to avoid locking user out permanently.
- [x] Process scanner matches case-insensitively and checks executable hashes where possible.

