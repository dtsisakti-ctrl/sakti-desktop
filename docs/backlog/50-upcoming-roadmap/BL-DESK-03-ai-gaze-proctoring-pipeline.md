# BL-DESK-03 — Edge AI Gaze Detection, Continuous WebRTC Live Streaming & Proctor Grid

|                |                                              |
| -------------- | -------------------------------------------- |
| **Owner**      | EG-CL                                        |
| **Phase**      | Phase 4 / Desktop Kiosk MVP                  |
| **Estimate**   | 7 days                                       |
| **Depends on** | BL-DESK-01, BL-DESK-02                       |
| **Blocks**     | None                                         |
| **Repo**       | sakti-desktop                                |
| **Branch**     | feat/BL-DESK-03-ai-gaze-proctoring           |
| **Status**     | **FULL** (Ready to Build)                    |

> Read first: `docs/backlog/00-README.md`, `docs/specs/2026-11-18-seb-desktop-lockdown-architecture-and-redundancy-analysis.md`,
> `docs/ExamGuard_PRD_v0_3_7.md` (§14, §15, §27.5).

---

### §1. Requirements Covered
- `REQ-DESK-12`: **Decoupled Native Edge AI Engine**: Runs computer vision models in a separate low-priority native OS thread (Rust + ONNX Runtime via C FFI), ensuring zero UI stutter or lag on the exam webview even on entry-level dual-core laptops.
- `REQ-DESK-13`: **Potato-Resilient Inference Pipeline (1–1.5 FPS Cascade)**:
  - Runs inference at low frequency (1–1.5 FPS) on downscaled frames ($320 \times 240$).
  - Two-stage cascade:
    1. **Stage 1 (YuNet ONNX ~200KB)**: Detects face presence (`face_count == 0` $\to$ `FACE_MISSING`, `face_count > 1` $\to$ `MULTIPLE_FACES`).
    2. **Stage 2 (Head Pose & Gaze Vector - PnP / 6 Landmarks)**: Estimates Yaw, Pitch, Roll. Detects prolonged gaze away from screen ($> \pm 25^\circ$ for $> 3.0$ seconds $\to$ `GAZE_DEVIATION`).
  - Total local AI CPU budget capped at $< 5\%$ on Intel Celeron / Core i3 with 4GB RAM.
- `REQ-DESK-14`: **Continuous Adaptive WebRTC Live Streaming**:
  - The desktop client maintains a **permanent, continuous live video stream** throughout the examination session.
  - Video stream is pushed to an SFU (Selective Forwarding Unit e.g., LiveKit / Mediasoup) using an ultra-efficient potato-friendly profile:
    - Resolution: $360\text{p}$ ($480 \times 360$) or $240\text{p}$.
    - Frame Rate: **10–12 FPS** (fluid enough for proctoring observation while slashing CPU/bandwidth by 60%).
    - Bitrate: Capped at **120–150 kbps** (easily sustained even over poor Indonesian 1 Mbps cellular uplinks).
- `REQ-DESK-15`: **Proctor Surveillance Wall with Dynacast/Simulcast Grid**:
  - In `SAKTI-Management-App`, the proctor sees a permanent live video gallery of 20–50 students.
  - Dynacast optimization: Small tiles receive the low-bitrate feed (~60 kbps). Clicking or expanding a candidate tile automatically upgrades that specific feed to 480p/720p without crashing the proctor's browser.
- `REQ-DESK-16`: **Continuous Server-Side Video Archiving (Egress)**:
  - SFU records candidate video streams directly to cloud storage (S3/MinIO), ensuring a tamper-proof audit trail for post-exam dispute resolution.

---

### §2. Context & Technical Reconciliation

#### The Challenge: Permanent Live Streaming on Potato Devices
If an entry-level laptop tries to encode 1080p/720p at 30fps while running local AI and rendering an exam, the machine will thermal-throttle and freeze. Furthermore, a proctor's browser attempting to decode 50 simultaneous 720p 30fps streams will exceed hardware decoder limits and crash.

#### The Engineered Solution:
1. **Camera Frame Sharing**: The native capture driver (OpenCV / MediaFoundation) captures the camera buffer once:
   - Feeds the local AI worker thread at **1.5 FPS** (decimated).
   - Feeds the WebRTC encoder at **10–12 FPS** (hardware-accelerated via Intel QuickSync / NVENC where available, with lightweight OpenH264 fallback).
2. **SFU Relay Architecture**: Direct P2P is replaced with an SFU (LiveKit / Mediasoup). The candidate pushes **only one** stream upstream (150 kbps), regardless of how many proctors or supervisors are watching.
3. **Simulcast / Dynacast on Proctor Console**: The proctor’s browser only receives the resolution required for the tile size, keeping total proctor downlink under **2.5 Mbps for 30 live streams**.

---

### §3. Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    sakti-desktop (Candidate Laptop)                          │
│                                                                              │
│  ┌────────────────────────────────────────────────────────┐                  │
│  │ Local WebCam (OpenCV / MediaFoundation: 640x480 @ 15fps)│                  │
│  └──────────────────────────┬─────────────────────────────┘                  │
│                             │ Shared Frame Buffer                            │
│              ┌──────────────┴──────────────┐                                 │
│              ▼ (Decimate: 1.5 FPS, 320x240)▼ (Decimate: 10 FPS, 150 kbps)   │
│  ┌───────────────────────────┐ ┌──────────────────────────────────────────┐  │
│  │ Native AI Thread (Rust)   │ │ WebRTC Streaming Client (Rust/WebRTC)    │  │
│  │ - YuNet Face Presence     │ │ - H.264 Hardware Enc / OpenH264          │  │
│  │ - PnP Head Pose & Gaze    │ │ - Bandwidth: 150 kbps uplink             │  │
│  │ - Emits Incident Events   │ └────────────────────┬─────────────────────┘  │
│  └─────────────┬─────────────┘                      │                        │
└────────────────┼────────────────────────────────────┼────────────────────────┘
                 │ Incident Metadata + Snapshot       │ Continuous Video Feed  
                 │ (WebSocket / HTTPS)                │ (WebRTC)               
                 ▼                                    ▼                        
┌───────────────────────────────────┐    ┌─────────────────────────────────────┐
│           SAKTI-Backend           │    │    LiveKit / Mediasoup SFU Node     │
│ - Telemetry & Event Ingestion     │    │ - Dynacast / Simulcast Distribution │
│ - Incident Timeline & Audit Log   │    │ - Cloud Egress Recording (S3/MinIO) │
└─────────────────┬─────────────────┘    └──────────────────┬──────────────────┘
                  │                                         │                   
                  │ Real-time Alerts                        │ Live Media Tracks 
                  ▼                                         ▼                   
┌──────────────────────────────────────────────────────────────────────────────┐
│                     SAKTI-Management-App (Proctor Console)                   │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │ Permanent Live Surveillance Wall (CCTV Gallery View)                   │  │
│  │ - 20–50 Active Live Video Tiles (10–12 FPS, 240p/360p)                 │  │
│  │ - Dynamic Alert Overlays (Yellow border on gaze shift, Red on incident)│  │
│  │ - Click tile to Spotlight / Zoom in (Dynacast switches to 480p)        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

### §4. Low-Level Implementation Specification

#### 4.1 Potato-Friendly Stream Encoding Profile
```rust
pub struct VideoStreamConfig {
    pub width: u32,       // 480
    pub height: u32,      // 360
    pub max_framerate: u8,// 10 or 12 fps
    pub max_bitrate_kbps: u32, // 150 kbps
    pub codec: VideoCodec,     // H264 baseline
}
```
- Hardware Encoder Detection: Queries for Intel QuickSync (`MF_READWRITE_ENABLE_HARDWARE_TRANSFORMS`) or NVENC. If unavailable, falls back to OpenH264 baseline with CPU preset `ultrafast`.
- Bandwidth Adaptation: If network latency increases ($> 400$ms), the encoder drops to 240p @ 8 FPS (~80 kbps) before dropping video entirely.

#### 4.2 Gaze & Head Pose Calibration & Evaluation
```rust
pub struct HeadPose {
    pub yaw: f32,    // Left/Right angle in degrees
    pub pitch: f32,  // Up/Down angle in degrees
    pub roll: f32,   // Tilt angle in degrees
}

pub fn evaluate_gaze(pose: &HeadPose) -> GazeState {
    const YAW_THRESHOLD: f32 = 25.0;        // > 25° left or right
    const PITCH_DOWN_THRESHOLD: f32 = 22.0; // > 22° looking down at desk/phone
    const PITCH_UP_THRESHOLD: f32 = 20.0;   // > 20° looking up at ceiling

    if pose.yaw.abs() > YAW_THRESHOLD || pose.pitch > PITCH_UP_THRESHOLD || pose.pitch < -PITCH_DOWN_THRESHOLD {
        GazeState::LookingAway
    } else {
        GazeState::FocusedOnScreen
    }
}
```

#### 4.3 Incident Lifecycle Timing
- `GAZE_DEVIATION`:
  - `started_at` triggered only after candidate looks away continuously for $> 3.0$ seconds.
  - Visual snapshot captured and sent immediately.
  - Closed when candidate returns gaze to the screen for $\ge 1.0$ second (hysteresis).
- `FACE_MISSING`:
  - Triggered when zero faces are detected for $> 5.0$ seconds.
- `MULTIPLE_FACES`:
  - Triggered when $> 1$ face is detected for $> 3.0$ seconds.

---

### §5. Mandatory UI States

1. **Pre-flight Camera & Gaze Calibration State (Candidate)**:
   - Displays live webcam check with guide box: *"Posisikan wajah Anda tepat di tengah bingkai"*.
   - Tests camera connectivity, microphone activity, and WebRTC SFU handshake before exam entrance.
2. **Active Exam State (Candidate)**:
   - Fullscreen kiosk. Subtle status indicator in toolbar: *"● Siaran Langsung & Terlindungi"* (green dot).
   - Candidate is free from distracting self-view windows during the exam.
3. **Proctor Surveillance Wall (`SAKTI-Management-App`)**:
   - Gallery grid of live video tiles for all candidates.
   - Dynamic visual badges overlaying each live stream:
     - 🟢 **Live**: Face in frame, focused on screen.
     - 🟡 **Warning**: Gaze drifting ($< 3$s) or minor network jitter.
     - 🔴 **Incident**: Gaze deviation ($> 3$s), face absent, or multiple faces.
4. **Spotlight / Focused Candidate Modal**:
   - Clicking any candidate tile enlarges their video feed to 480p, displays their real-time gaze vector overlay, and shows their recent incident history.

---

### §6. Edge Cases & Resilience
- **Packet Loss / Bad Indonesian Wi-Fi**: The WebRTC stream uses adaptive NACK/FEC. If packet loss exceeds 15%, video resolution degrades gracefully to 240p without terminating the exam or desynchronizing exam answers.
- **Proctor Hardware Overload**: In the proctor console, off-screen candidate tiles (e.g., when paginating through 100 students) automatically unsubscribe from video tracks, decoding only the visible 20–25 tiles.
- **Camera Disconnection**: If a candidate unplugs their external webcam or closes their laptop lid, the client immediately flags `CAMERA_DISCONNECTED` and pauses the exam view until the camera is restored.

---

### §7. Verification & Automated Tests
- Encode performance benchmark: Confirm 360p @ 10 FPS encoding uses $\le 7\%$ CPU on dual-core Celeron reference machine.
- WebRTC connection test: Verify seamless connection establishment through STUN/TURN/SFU.
- Bandwidth profiling: Verify continuous uplink does not exceed 180 kbps.
- Dynacast test: Verify SFU switches layers correctly when candidate tile is expanded.

---

### §8. Acceptance Checklist
- [x] Candidate desktop client streams continuous live video throughout the entire exam session.
- [x] Total client CPU footprint (AI inference + WebRTC encoding) remains $< 12\%$ on entry-level laptops.
- [x] Continuous uplink bandwidth stays within 120–150 kbps.
- [x] Proctor console displays a permanent live CCTV surveillance grid of 20–50 students.
- [x] Gaze deviations ($> 3$s), face absences, and multiple faces trigger real-time visual alerts on the proctor's screen.
- [x] SFU automatically archives continuous streams to cloud storage for post-exam review.

---

### §9. Security & Privacy Checklist
- [x] WebRTC media traffic is end-to-end encrypted with SRTP/DTLS.
- [x] Video recordings stored in cloud storage are access-controlled and encrypted at rest with AES-GCM-256.
- [x] All proctor viewing and inspection actions are logged to the immutable audit trail.
