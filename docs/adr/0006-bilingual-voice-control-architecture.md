# 0006 — Bilingual Voice Control Architecture & State Management

## Status
Accepted

## Date
2026-08-17

## Context

BAZspark is an engineering design platform for NFPA 72 fire alarm and electrical systems, requiring rapid interaction during spatial layout, device placement, and conversational AI engineering copilot sessions (`AgentChatPage`, `AskAiSheet`). 

Engineers and inspectors operating in field conditions or multi-screen BIM setups require hands-free and rapid voice interaction. The platform serves bilingual engineering teams working in both Arabic (primarily Egyptian dialect `ar-EG` and Modern Standard Arabic) and English (`en-US`).

Key architectural challenges:
1. **Web Speech API Fragmentation:** The W3C `SpeechRecognition` interface is non-uniform across browsers (e.g., `webkitSpeechRecognition` in Chromium-based browsers, absent in some Firefox/Safari configurations).
2. **Security & Prompt Injection:** Audio transcripts delivered to LLMs and state stores are untrusted input. Voice transcriptions can contain malformed control characters, script tags, or prompt injection payloads.
3. **Bilingual Intent & Locale Matching:** Language changes in the UI (`i18n.language`) must dynamically reconfigure speech recognition engines without requiring manual page reloads or dropping active recognition sessions.
4. **Dual Capabilities (Live STT vs. Raw Audio Blobs):** Consumers require both real-time interim/final text recognition and recorded audio blobs (`Blob`) for downstream backend Whisper/AI storage.

## Decision

We implement a dedicated, hook-based speech subsystem encapsulated in `frontend/src/hooks/useVoiceControl.ts` with the following architectural design:

### 1. Cross-Browser Engine Resolution & Fallback Detection

The hook detects the available speech engine at runtime via window polymorphism:
```typescript
const SpeechRecognitionAPI: SpeechRecognitionConstructor | undefined =
  (window as unknown as { SpeechRecognition?: SpeechRecognitionConstructor }).SpeechRecognition ||
  (window as unknown as { webkitSpeechRecognition?: SpeechRecognitionConstructor }).webkitSpeechRecognition;
```
If unavailable, `isSupported` evaluates to `false`, and the hook gracefully degrades to standard `MediaRecorder` audio capture (`isMediaRecorderSupported`) with descriptive user toast notifications.

### 2. Dynamic i18n Locale Resolution

The recognition locale dynamically binds to the active application locale:
- Arabic contexts (`ar`, `ar-EG`, `ar-SA`) resolve to `ar-EG`.
- All other contexts resolve to `en-US`.
- Explicit `lang` overrides passed via `VoiceControlOptions` take precedence.

### 3. Voice Input Sanitization Gate

Before any transcript reaches state stores (`simpleStore`) or AI query handlers, it passes through `sanitizeVoiceInput()`:
- Strips ASCII & Unicode control characters (`[\u0000-\u001F\u007F-\u009F]`).
- Neutralizes backticks (`` ` ``), template interpolation tokens (`${...}`), and escape backslashes (`\`).
- Normalizes irregular whitespace.

### 4. Bilingual Command Processing & State Store Integration

The command parser matches natural voice phrasing across Arabic and English to trigger state mutations:
- **Generators:** `"add generator"`, `"اضف مولد"`, `"إضافة مولد"`, `"مولد"` → Dispatches `ADD_GENERATOR` (`voltage: 11000V`).
- **Batteries:** `"add battery"`, `"اضف بطارية"`, `"إضافة بطارية"`, `"بطارية"` → Dispatches `ADD_BATTERY` (`voltage: 24V`).
- **Canvas / Error Cleanup:** `"clear errors"`, `"امسح الاخطاء"`, `"مسح الأخطاء"` → Dispatches `clearErrors()`.
- **Operating Modes:** `"simulation mode"`, `"demo mode"`, `"وضع المحاكاة"` → Dispatches `setDataMode()`.

### 5. Memory & Lifecycle Safety

- Speech recognition instances and `MediaRecorder` streams are tracked using `useRef` handles.
- All media tracks (`stream.getTracks()`) are explicitly stopped on recording termination.
- Event listeners (`onresult`, `onerror`, `onend`, `onstart`) are cleanly detached on unmount.

---

## Alternatives Considered

### 1. Heavy Client-Side WebAssembly STT (e.g. Whisper Web/Transformers.js)
- **Pros:** Completely offline, browser-independent.
- **Cons:** 40MB–150MB initial model download; significant CPU/GPU memory footprint in browser tab; unacceptable latency on lower-end tablets/laptops.
- **Rejected:** Native Web Speech API delivers zero bundle footprint with sub-200ms latency.

### 2. Third-Party Proprietary Cloud SDKs (e.g. Agora, Deepgram, Google Cloud Speech)
- **Pros:** High accuracy across rare dialects.
- **Cons:** Adds vendor lock-in, client-side API secret exposure risks, network overhead, and subscription costs.
- **Rejected:** Built-in Web Speech API + backend Whisper fallback provides the cleanest security posture and cost profile.

### 3. Server-Only Audio Streaming (WebSocket PCM Streaming)
- **Pros:** Centralized speech engine.
- **Cons:** High bandwidth requirement, server CPU scaling bottlenecks, latency for basic UI commands (e.g., zooming or switching modes).
- **Rejected:** Client-side recognition with local fallback provides instantaneous feedback.

---

## Consequences

- **Zero Runtime Dependencies:** Utilizes standardized browser Web Speech API and MediaRecorder without increasing bundle size.
- **Bilingual Support:** Seamlessly switches between Arabic (`ar-EG`) and English (`en-US`) in synchronization with the UI language switcher.
- **High Testability:** The hook is isolated and 100% covered by comprehensive mock unit tests in `frontend/src/hooks/__tests__/useVoiceControl.test.ts`.
- **Security Compliance:** Sanitized input guarantees no unescaped control codes or prompt injection vectors enter LLM context streams or simpleStore state reducers.
