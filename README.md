# SodaAgent

**Your AI-powered car voice assistant** - Built for the [Gemini Live Agent Challenge](https://geminiliveagentchallenge.devpost.com/)

SodaAgent is an always-on voice assistant for drivers, powered by Google's Gemini Live API and Agent Development Kit (ADK). It provides hands-free access to calendar, navigation, weather, music, and messaging through natural voice conversation.

**Key differentiator**: SodaAgent can proactively call you on your phone (via Twilio PSTN) when important events are approaching, even when you're not using the app.

## Architecture

```
┌────────────┐  WebSocket    ┌──────────────────┐    Gemini
│ Flutter App │ ◄───────────► │ Cloud Run (ADK)  │ ◄──────► Live API
│ (Voice)     │  PCM 16kHz    │ FastAPI          │
└────────────┘               └────────┬─────────┘
                                      │
┌────────────┐  PSTN Call    ┌────────▼─────────┐
│ Your Phone │ ◄────────────► │ Twilio Media     │
│ (Any phone)│  mulaw 8kHz   │ Streams          │
└────────────┘               └────────▲─────────┘
                                      │
                  Cloud Scheduler ─────┘ (trigger evaluation)
```

## Features

- **Real-time voice conversation** via Gemini Live API bidirectional audio streaming
- **Multi-agent architecture**: Calendar, Navigation, Weather, Music, Messaging, General
- **Proactive outbound calls**: Agent calls you via Twilio when calendar events approach
- **Always-on connection** with automatic session resumption

## Tech Stack

| Component | Technology |
|-----------|-----------|
| AI Model | Gemini 2.0 Flash (Native Audio) |
| Agent Framework | Google ADK (Agent Development Kit) |
| Backend | Python + FastAPI |
| Mobile | Flutter |
| Telephony | Twilio (PSTN + Media Streams) |
| Cloud | Google Cloud Run, Firestore, Cloud Scheduler |

## Getting Started

### Prerequisites

- Python 3.10+
- Google API Key ([Get one here](https://aistudio.google.com/apikey))
- Twilio account (for outbound calls)

### Local Development

```bash
# 1. Set up backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure API key
cp ../infrastructure/env/.env.example soda_agent/.env
# Edit soda_agent/.env and set GOOGLE_API_KEY

# 3. Run with ADK Developer UI
adk web soda_agent

# Or run FastAPI server
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

### Deploy to GCP

```bash
export GOOGLE_CLOUD_PROJECT=your-project-id
./infrastructure/deploy.sh
```

## Project Structure

```
SodaAgent/
├── backend/
│   ├── main.py              # FastAPI entrypoint
│   ├── soda_agent/          # ADK agent package
│   │   ├── agent.py         # Root agent + sub-agents
│   │   ├── sub_agents/      # Calendar, Nav, Weather, Music, Messaging, General
│   │   └── tools/           # Tool implementations
│   ├── services/            # Audio bridge, Twilio, triggers, sessions
│   └── routers/             # WebSocket + REST endpoints
├── mobile/                  # Flutter app
├── infrastructure/          # Dockerfile, deploy scripts
└── docs/                    # Architecture docs
```

## Development Progress

### Phase 1: Core Voice Loop (Day 1-5)

| Day | Task | Status |
|-----|------|--------|
| Day 1 | 프로젝트 스캐폴딩 + ADK 설치 | ✅ Complete |
| Day 2 | FastAPI + WebSocket + Cloud Run 배포 | ✅ Complete |
| Day 3 | 양방향 오디오 스트리밍 (Live API) | ✅ Complete |
| Day 4 | Flutter 앱 기본 (mic + WS + UI) | ✅ Complete |
| Day 5 | E2E 음성 루프 검증 + 트랜스크립션 | 🔄 In Progress |

### Phase 2: Multi-Agent + Twilio (Day 6-9)

| Day | Task | Status |
|-----|------|--------|
| Day 6 | Sub-agents + mock tools 완성 | 📋 Pending |
| Day 7 | Google Calendar API 실제 연동 | 📋 Pending |
| Day 8 | Twilio 설정 + audio_bridge | 📋 Pending |
| Day 9 | 아웃바운드 콜 E2E | 📋 Pending |

### Phase 3: Polish + 제출 (Day 10-14)

| Day | Task | Status |
|-----|------|--------|
| Day 10 | Cloud Scheduler + 프로액티브 트리거 | 📋 Pending |
| Day 11 | Flutter UI 폴리시 | 📋 Pending |
| Day 12 | 인프라 정리 + 아키텍처 다이어그램 | 📋 Pending |
| Day 13 | 데모 영상 촬영 (4분) | 📋 Pending |
| Day 14 | 버퍼 + Devpost 제출 | 📋 Pending |

### Key Technical Decisions

- **Live API**: `gemini-2.5-flash-native-audio-preview-12-2025` (bidiGenerateContent only)
- **Flat agent for live mode**: `live_agent` with all 14 tools directly (no sub-agents) — `transfer_to_agent` doesn't work with bidiGenerateContent
- **Text mode**: `root_agent` with 6 sub-agents using `gemini-2.5-pro`
- **Thought filtering**: Server-side `part.thought` check to skip model thinking tokens
- **Audio transcription**: ADK surfaces `event.output_transcription` / `event.input_transcription` (not in `event.content.parts`)

## Category

**Live Agents** - Real-time voice/vision interaction with proactive outbound communication.

## License

MIT
