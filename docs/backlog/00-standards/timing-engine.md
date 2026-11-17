# 00-standards/timing-engine: Precision Timing Engine (PRD §11)

---

## 1. Timing Formulas

ExamGuard calculates deadlines using two distinct modes:

### 1.1 FIXED_END Mode
The exam has a rigid global closing time.
$$\text{deadline} = \min(\text{started\_at} + \text{duration} + \text{accommodation}, \text{window\_end})$$
*Late start consumes personal test time.*

### 1.2 FULL_DURATION Mode
Each candidate receives their full allocated time regardless of when they start within the open check-in window.
$$\text{deadline} = \text{started\_at} + \text{duration} + \text{accommodation}$$

---

## 2. Pause Modes (PRD §11.2)

When an invigilator pauses an attempt:
- `PAUSE_TIMER`: Remaining duration freezes. Upon resume, deadline shifts forward:
  $$\text{new\_deadline} = \text{old\_deadline} + (\text{resumed\_at} - \text{paused\_at})$$
- `KEEP_RUNNING`: Clock continues running in the background. Used during brief biometric identity verifications.

---

## 3. Clock Offset Synchronization
All client deadlines are calculated server-side. The client tracks server clock offset:
$$\text{clock\_offset} = \text{server\_time} - \text{local\_client\_time}$$
Countdown displays render normalized against the authoritative server time, preventing client-side clock tampering.

