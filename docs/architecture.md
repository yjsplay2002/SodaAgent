# SodaAgent 아키텍처 구조도

## 1. 전체 시스템 개요

```
┌─────────────────────────────────────────────────────────────────────┐
│                         SODA AGENT SYSTEM                           │
│                                                                     │
│  ┌──────────────┐    WebSocket     ┌──────────────────────────────┐ │
│  │  Flutter App  │◄────────────────►│   FastAPI Backend (GCP)      │ │
│  │  (Mobile)    │   JSON+PCM audio │   (Cloud Run)                │ │
│  └──────────────┘                  └──────────────┬───────────────┘ │
│                                                   │                 │
│                                    ┌──────────────▼───────────────┐ │
│                                    │    Google ADK Runner          │ │
│                                    │  (bidiGenerateContent)        │ │
│                                    └──────────────┬───────────────┘ │
│                                                   │                 │
│                                    ┌──────────────▼───────────────┐ │
│                                    │   Gemini Live API             │ │
│                                    │ (gemini-live-2.5-flash-       │ │
│                                    │  native-audio)                │ │
│                                    └──────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. 에이전트 구조: 두 가지 모드

```
┌─────────────────────────────────────────────────────────────────────┐
│                         agent.py                                    │
│                                                                     │
│  ┌──────────────────────────────┐  ┌──────────────────────────────┐ │
│  │       TEXT MODE              │  │      LIVE AUDIO MODE         │ │
│  │                              │  │                              │ │
│  │  root_agent (soda_agent)     │  │  live_agent                  │ │
│  │  Model: gemini-2.5-pro       │  │  Model: gemini-live-2.5-     │ │
│  │  Pattern: Multi-agent        │  │         flash-native-audio   │ │
│  │          (Sub-agent 위임)     │  │  Pattern: Flat (단일 에이전트) │ │
│  │                              │  │                              │ │
│  │  ┌──────────────────────┐    │  │  ┌────────────────────────┐  │ │
│  │  │    Sub-Agents (6)    │    │  │  │    All 14 Tools        │  │ │
│  │  │                      │    │  │  │  (직접 연결, 위임 없음)  │  │ │
│  │  │ • calendar_agent     │    │  │  │                        │  │ │
│  │  │ • navigation_agent   │    │  │  │ Calendar (3)           │  │ │
│  │  │ • weather_agent      │    │  │  │ Navigation (3)         │  │ │
│  │  │ • music_agent        │    │  │  │ Weather (2)            │  │ │
│  │  │ • messaging_agent    │    │  │  │ Music (3)              │  │ │
│  │  │ • general_agent      │    │  │  │ Messaging (2)          │  │ │
│  │  └──────────────────────┘    │  │  │ Vehicle (1)            │  │ │
│  │                              │  │  └────────────────────────┘  │ │
│  │  ※ 현재 미사용               │  │                              │ │
│  │    (ws_mobile은 live_agent만) │  │  ← 실제 사용되는 모드         │ │
│  └──────────────────────────────┘  └──────────────────────────────┘ │
│                                                                     │
│  이유: bidiGenerateContent는 transfer_to_agent 미지원                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Live Agent 툴 구조 (14개)

```
                    ┌─────────────────────────────┐
                    │         live_agent           │
                    │  (gemini-live-2.5-flash-     │
                    │   native-audio)              │
                    └──────────────┬──────────────┘
                                   │
          ┌────────────────────────┼──────────────────────────┐
          │                        │                          │
          ▼                        ▼                          ▼
┌──────────────────┐  ┌────────────────────┐  ┌─────────────────────┐
│  calendar_tools  │  │   maps_tools       │  │   weather_tools     │
│                  │  │   (실제 Google API) │  │   (Mock)            │
│ get_upcoming_    │  │                    │  │                     │
│   events()       │  │ get_directions()   │  │ get_current_        │
│ create_event()   │  │ get_eta()          │  │   weather()         │
│ get_free_slots() │  │ search_places()    │  │ get_forecast()      │
│                  │  │                    │  │                     │
│ (Mock)           │  │ (Google Maps API)  │  │                     │
└──────────────────┘  └────────────────────┘  └─────────────────────┘

┌──────────────────┐  ┌────────────────────┐  ┌─────────────────────┐
│  music_tools     │  │  messaging_tools   │  │  vehicle_tools      │
│  (Mock)          │  │  (Mock)            │  │  (Mock)             │
│                  │  │                    │  │                     │
│ play_song()      │  │ read_messages()    │  │ get_vehicle_        │
│ pause_music()    │  │ send_message()     │  │   status()          │
│ skip_track()     │  │                    │  │                     │
└──────────────────┘  └────────────────────┘  └─────────────────────┘
                                   +
                    ┌──────────────────────┐
                    │  google_search       │
                    │  (ADK Built-in)      │
                    └──────────────────────┘
```

---

## 4. 백엔드 서비스 레이어

```
┌─────────────────────────────────────────────────────────────────────┐
│                       FastAPI (main.py)                             │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                         Routers                              │   │
│  │                                                              │   │
│  │  /ws/mobile/{user_id}    /ws/twilio/{call_id}               │   │
│  │  ws_mobile.py ◄──────    ws_twilio.py (예정)                │   │
│  │  [현재 메인 경로]                                             │   │
│  │                                                              │   │
│  │  /trigger/check-calendar  /twilio/events    GET /           │   │
│  │  scheduler_handler.py     twilio_webhooks   health.py       │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                        Services                              │   │
│  │                                                              │   │
│  │  ┌─────────────────┐  ┌──────────────┐  ┌───────────────┐  │   │
│  │  │ SessionManager  │  │ AudioBridge  │  │ TwilioService │  │   │
│  │  │                 │  │              │  │               │  │   │
│  │  │ InMemorySession │  │ mulaw 8kHz   │  │ PSTN 발신     │  │   │
│  │  │ Service (MVP)   │  │ ↕           │  │ TwiML 생성    │  │   │
│  │  │                 │  │ PCM 16/24kHz│  │               │  │   │
│  │  │ → Firestore(예정)│  └──────────────┘  └───────────────┘  │   │
│  │  └─────────────────┘                                        │   │
│  │                                                              │   │
│  │  ┌─────────────────┐                                        │   │
│  │  │  TriggerEngine  │                                        │   │
│  │  │                 │                                        │   │
│  │  │  일정 기반       │                                        │   │
│  │  │  자동 발신 트리거│                                        │   │
│  │  └─────────────────┘                                        │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 5. 실시간 오디오 데이터 흐름

```
Flutter App                 Backend (ws_mobile.py)           Gemini Live
──────────                 ──────────────────────           ──────────
   │                               │                             │
   │  PCM 16kHz mono               │                             │
   │─────{"type":"audio"}─────────►│  LiveRequestQueue           │
   │                               │──────────────────────────► │
   │                               │                    (음성인식)│
   │                               │◄──────── transcript(user) ──│
   │◄──{"type":"transcript",       │                             │
   │    "role":"user", "text":"…"} │                    (도구선택)│
   │                               │◄──── tool function_call ───│
   │◄──{"type":"tool_call",…}      │  execute tool()             │
   │                               │  inject result              │
   │                               │──────── tool result ───────►│
   │                               │                   (응답생성) │
   │                               │◄──── PCM audio 24kHz ───────│
   │◄──{"type":"audio", "data":"…"}│                             │
   │   AudioService.feedAudio()    │◄──── transcript(model) ──── │
   │◄──{"type":"transcript",       │                             │
   │    "role":"model","text":"…"} │                             │
   │◄──{"type":"turn_complete"}    │◄──── turn_complete ─────────│
   │   WAV 파일로 저장              │                             │
   │   재생 버튼 활성화              │                             │
```

---

## 6. Flutter 앱 상태 관리

```
┌─────────────────────────────────────────────────────────┐
│                   Flutter (Riverpod)                    │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │           VoiceSessionNotifier                   │   │
│  │           (StateNotifier)                        │   │
│  │                                                  │   │
│  │  State: VoiceSessionState                        │   │
│  │  ├─ voiceState: idle/listening/thinking/speaking │   │
│  │  ├─ connectionState: disconnected/connecting/    │   │
│  │  │                   connected/error             │   │
│  │  ├─ transcripts: List<TranscriptEntry>           │   │
│  │  ├─ currentToolCall: String?                     │   │
│  │  └─ playingAudioPath: String?                    │   │
│  └──────────────────┬───────────────────────────────┘   │
│                     │                                   │
│          ┌──────────┴───────────┐                       │
│          ▼                      ▼                       │
│  ┌───────────────┐   ┌──────────────────┐               │
│  │WebSocketService│   │  AudioService    │               │
│  │               │   │                  │               │
│  │ WS 연결/재연결 │   │ 마이크 캡처       │               │
│  │ base64 인코딩  │   │ 스피커 재생       │               │
│  │ JSON 송수신    │   │ WAV 파일 저장     │               │
│  └───────────────┘   └──────────────────┘               │
│                                                         │
│  UI Components                                          │
│  ├─ VoiceOrb         (상태별 색상 애니메이션)             │
│  ├─ TranscriptOverlay (대화 기록 + 재생 버튼)             │
│  └─ HomeScreen       (연결 상태 + 텍스트 입력)            │
└─────────────────────────────────────────────────────────┘
```

---

## 7. 웹소켓 메시지 프로토콜

### Client → Server

```json
{"type": "audio", "data": "<base64 PCM 16-bit 16kHz mono>"}
{"type": "text", "text": "hello world"}
{"type": "end_turn"}
```

### Server → Client

```json
{"type": "audio", "data": "<base64 PCM audio>", "mime_type": "audio/pcm;rate=24000"}
{"type": "transcript", "role": "model", "text": "What can I help you with?"}
{"type": "transcript", "role": "user", "text": "Tell me a joke"}
{"type": "tool_call", "name": "search_places", "args": {"query": "coffee shop"}}
{"type": "turn_complete"}
{"type": "interrupted"}
{"type": "error", "message": "..."}
```

### 오디오 포맷 스펙

| 방향 | 포맷 | 샘플레이트 | 채널 | 비트 |
|------|------|-----------|------|------|
| Mobile → Gemini (입력) | PCM | 16 kHz | Mono | 16-bit |
| Gemini → Mobile (출력, Aoede 음성) | PCM | 24 kHz | Mono | 16-bit |
| Twilio ↔ Backend | mulaw | 8 kHz | Mono | 8-bit |

---

## 8. 핵심 설계 포인트

| 항목 | 내용 |
|------|------|
| **Live Agent가 Flat인 이유** | `bidiGenerateContent`가 `transfer_to_agent` 미지원 → 14개 툴을 직접 연결 |
| **Nudge 로직** | 툴 실행 후 모델이 발화하지 않을 때 결과를 텍스트로 재주입 |
| **Barge-in** | 모델 발화 중 사용자 입력 감지 시 오디오 즉시 중단 |
| **오디오 포맷** | 입력: PCM 16kHz / 출력: PCM 24kHz / Twilio: mulaw 8kHz |
| **WAV 저장** | 모델 응답 오디오를 파일로 누적 저장 → 재생 버튼으로 복원 |
| **세션** | MVP: InMemorySessionService → 향후 Firestore 전환 예정 |

---

## 9. 디렉토리 구조

```
SodaAgent/
├── backend/
│   ├── main.py                      # FastAPI 진입점
│   ├── requirements.txt
│   ├── soda_agent/
│   │   ├── agent.py                 # root_agent & live_agent 정의
│   │   ├── prompts.py               # 에이전트 지시문
│   │   ├── sub_agents/              # 6개 전문 서브 에이전트 (text mode용)
│   │   │   ├── calendar_agent.py
│   │   │   ├── navigation_agent.py
│   │   │   ├── weather_agent.py
│   │   │   ├── music_agent.py
│   │   │   ├── messaging_agent.py
│   │   │   └── general_agent.py
│   │   └── tools/                   # 14개 툴 구현
│   │       ├── calendar_tools.py
│   │       ├── maps_tools.py        # 실제 Google Maps API 연동
│   │       ├── weather_tools.py
│   │       ├── music_tools.py
│   │       ├── messaging_tools.py
│   │       └── vehicle_tools.py
│   ├── services/
│   │   ├── session_manager.py       # ADK 세션 라이프사이클
│   │   ├── audio_bridge.py          # mulaw ↔ PCM 변환
│   │   ├── twilio_service.py        # PSTN 발신 관리
│   │   └── trigger_engine.py        # 프로액티브 발신 트리거
│   └── routers/
│       ├── ws_mobile.py             # Flutter 앱 WebSocket (메인)
│       ├── ws_twilio.py             # PSTN 통화 WebSocket (예정)
│       ├── scheduler_handler.py     # Cloud Scheduler 웹훅
│       ├── twilio_webhooks.py       # Twilio 이벤트 콜백
│       └── health.py                # 헬스체크
├── mobile/
│   └── lib/
│       ├── main.dart
│       ├── screens/home_screen.dart
│       ├── services/
│       │   ├── voice_session.dart   # Riverpod StateNotifier
│       │   ├── websocket_service.dart
│       │   └── audio_service.dart
│       └── widgets/
│           ├── voice_orb.dart
│           └── transcript_overlay.dart
├── infrastructure/
│   ├── deploy.sh
│   └── Dockerfile
└── docs/
    ├── architecture.md              # 이 문서
    └── gemini-models.md
```
