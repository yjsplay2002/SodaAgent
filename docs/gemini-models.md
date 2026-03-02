# Gemini Models Reference (2026.03)

## SodaAgent 모델 설정 (현재 적용, 검증 완료)

| 에이전트 | 모델 ID | API 메서드 | 용도 |
|---------|---------|-----------|------|
| **Root Agent (text)** | `gemini-2.5-pro` | generateContent | 텍스트 모드 라우팅/추론 |
| **Root Agent (live)** | `gemini-2.5-flash-native-audio-preview-12-2025` | bidiGenerateContent | 양방향 오디오 스트리밍 |
| **Sub Agents (6개)** | `gemini-2.5-flash` | generateContent | 도구 호출 (안정적, 빠름) |

> **주의**: Live API 모델(`*native-audio*`)은 `generateContent`를 지원하지 않음.
> 텍스트 모드와 라이브 스트리밍 모드에서 서로 다른 모델이 필요함.
> 라이브 오디오 모델은 `routers/ws_mobile.py`의 RunConfig에서 설정.
> `gemini-3.1-pro-preview-customtools`는 최고 성능이지만 503 과부하 빈발 → 안정성 위해 `gemini-2.5-flash` 사용.

## Live API (bidiGenerateContent) 지원 모델

| 모델 ID | 상태 | 비고 |
|---------|------|------|
| `gemini-2.5-flash-native-audio-preview-12-2025` | **현재 활성 (최선)** | AI Studio 키 호환, Thinking 모드, 30 HD voices |
| `gemini-2.5-flash-native-audio-preview-09-2025` | 구버전 | 12-2025보다 덜 capable |
| `gemini-live-2.5-flash-native-audio` | Vertex AI 전용 (GA) | AI Studio 키 사용 불가 |

> Pro급 Live API 모델은 없음. Live API는 Flash 계열만 지원.

## Tool Calling 모델 (generateContent)

| 모델 ID | 티어 | 비고 |
|---------|------|------|
| `gemini-3.1-pro-preview-customtools` | **최고 (에이전트 특화)** | 커스텀 도구 우선 호출, 2026.02.19 출시 |
| `gemini-3.1-pro-preview` | 최고 (범용) | 동일 성능, 범용 행동 |
| `gemini-2.5-pro` | GA (안정) | STEM/코드 강점 |
| `gemini-3-flash-preview` | 빠른 프론티어 | Flash 속도 + Gemini 3급 지능 |
| `gemini-2.0-flash` | 레거시 | 2세대 뒤처짐 |

## 종료된 / 종료 예정 모델

| 모델 ID | 상태 |
|---------|------|
| `gemini-2.0-flash-live-001` | 종료 (2025.12.09) |
| `gemini-live-2.5-flash-preview` | 종료 (2025.12.09) |
| `gemini-3-pro-preview` | **종료 예정 (2026.03.26)** |
| `gemini-2.0-flash-exp` | 종료 예정 (2026.06.01) |

## API 버전

- **v1beta** 사용 (v1alpha 아님)
- WebSocket: `wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent`
- ADK v1.3.0+ 필요 (현재 v1.26.0 설치됨, 호환)
