# Session Recovery Plan

## Goal

현재는 WebSocket 연결이 열릴 때마다 새 ADK 세션을 만들고, 연결이 끊기면 사실상 대화 연속성이 사라진다.

이번 변경의 목표는 다음과 같다.

- ADK 실제 세션 저장소는 계속 `InMemory`로 유지한다.
- 서버는 사용자별 세션 메타데이터와 최근 턴 요약을 별도 인메모리 카탈로그로 관리한다.
- 사용자가 재접속한 뒤 새 요청을 보냈을 때:
  - 기존 세션과 연관성이 높으면 기존 세션을 복구한다.
  - 독립형 질문이면 새 세션을 연다.
- 클라이언트에서 세션 목록을 조회하고 직접 선택할 수 있게 한다.
- 장기적으로 Firestore로 옮기기 쉽도록 저장 계층 경계를 분리한다.

## Non-Goal

- 이번 단계에서 Firestore를 실제로 붙이지 않는다.
- Twilio 세션 복구까지 확장하지 않는다.
- 기존 음성 UX를 전면 재설계하지 않는다.

## Current Problems

- `ws_mobile`가 WebSocket 연결 시점에 바로 `create_session()`을 호출한다.
- `conversation_id`는 UI 식별자에 가깝고, 실제 ADK 세션 복구에는 쓰이지 않는다.
- 세션 목록 조회 API가 없다.
- 모바일은 단일 `conversation_id`만 저장하고 있고, 과거 세션 목록이나 선택 UI가 없다.

## Proposed Architecture

### 1. Two-layer session model

- Layer 1: `ADK session`
  - 실제 모델 컨텍스트가 들어 있는 런타임 세션
  - 현재는 `InMemorySessionService`로 유지
- Layer 2: `conversation catalog`
  - 사용자별 대화 목록, 제목, 최근 메시지, 최근 턴, 마지막 활동 시각, 도메인, 현재 바인딩된 ADK 세션 참조를 관리
  - 이번 단계에서는 서버 메모리 dict 기반
  - 이후 Firestore 저장소로 치환 가능한 인터페이스를 유지

### 2. Conversation catalog responsibilities

새 서비스 `conversation_store`가 아래를 담당한다.

- 사용자별 세션 목록 보관
- `conversation_id -> ADK session` 매핑 보관
- 최근 최종 user/assistant 턴 저장
- 세션 제목/미리보기 생성
- 세션 선택/복구/신규 생성 결정
- 세션 목록/세션 상세 API 응답 생성

## Session Resolution Policy

### Explicit selection wins

클라이언트가 특정 `conversation_id`를 선택해서 보낸 경우:

- 해당 세션이 있으면 무조건 복구
- 없으면 새 세션 생성

### Automatic resolution for text turns

텍스트 요청은 첫 user turn의 실제 문자열이 있으므로 아래 순서로 판정한다.

1. follow-up 신호가 있는지 확인
2. 독립형 utility 질문인지 확인
3. 기존 세션 relevance score 계산
4. score가 기준 이상이면 기존 세션 복구, 아니면 새 세션 생성

### Heuristic rules

#### Follow-up signals

아래 표현이 있으면 기존 세션 복구를 우선한다.

- 한국어: `이어서`, `아까`, `그거`, `그 일정`, `그 노래`, `거기`, `방금`, `계속`
- 영어: `continue`, `that`, `it`, `there`, `again`, `same one`, `earlier`, `previous`

#### Standalone utility queries

아래 성격의 질문은 기본적으로 새 세션을 연다.

- 오늘/내일 날씨, 기온, 비
- ETA, 길찾기, 목적지까지 몇 분, 교통 상황
- 근처 장소 검색
- 짧은 일반 utility 질문

단, follow-up 신호가 있으면 standalone으로 보지 않는다.

#### Relevance scoring

기존 세션 score는 다음 요소를 합산한다.

- 최근성: 마지막 활동 시각
- 토큰 겹침: 새 질문 vs 세션 제목/최근 user turn
- 도메인 일치: calendar/music/messaging 등
- 세션 상태: 최근 활성 세션인지 여부

기본 전략:

- follow-up 신호 + 최근 세션 존재 -> 가장 최근 관련 세션 복구
- standalone utility -> 새 세션
- 그 외 -> score 높은 세션이 threshold 초과 시 복구

### Automatic resolution for audio turns

오디오의 첫 턴은 서버가 의미를 알기 전에 ADK 세션 바인딩이 필요하다. 이번 단계에서는 아래 정책으로 간다.

- 명시적으로 선택된 `conversation_id`가 있으면 그 세션에 바인딩
- 없으면 최근 continuable 세션이 있으면 복구
- 그 외에는 새 세션 생성

즉, 텍스트보다 오디오 자동 분기는 보수적으로 간다. 세션 목록에서 수동 선택이 가능하도록 해서 이 한계를 보완한다.

## Backend Changes

### 1. New conversation store service

예상 파일:

- `backend/services/conversation_store.py`

주요 데이터:

- `ConversationSummary`
- `ConversationTurn`
- `ConversationRecord`

주요 기능:

- `list_conversations(user_id)`
- `get_conversation(user_id, conversation_id)`
- `resolve_conversation(user_id, text, preferred_conversation_id)`
- `resolve_for_audio(user_id, preferred_conversation_id)`
- `bind_adk_session(...)`
- `append_turn(...)`
- `touch(...)`

### 2. WebSocket lifecycle refactor

`ws_mobile.py` 변경 방향:

- 연결 시점에 ADK 세션을 즉시 만들지 않는다.
- 첫 유효 turn에서 세션을 resolve/bind 한다.
- resolve 결과가 기존 세션이면 기존 ADK 세션을 재사용한다.
- resolve 결과가 신규 세션이면 그때 ADK 세션을 생성한다.
- 최종 user/assistant 턴이 커밋될 때 conversation store에도 반영한다.

### 3. Session APIs

새 라우터 추가:

- `GET /api/sessions/{user_id}`
  - 세션 목록 반환
- `GET /api/sessions/{user_id}/{conversation_id}`
  - 세션 상세 + 최근 턴 반환

필요 시 후속 단계에서:

- `POST /api/sessions/{user_id}/new`
- `POST /api/sessions/{user_id}/select`

하지만 이번 단계는 WebSocket + 조회 API만으로 충분하다.

## Client Changes

### 1. Session list state

`VoiceSessionState`에 추가:

- session list
- selected conversation id
- loading/error state

### 2. Session catalog service

새 모바일 서비스 추가:

- 세션 목록 조회
- 세션 상세 조회

### 3. Selection UX

`HomeScreen` 상단에서:

- 세션 목록 버튼
- bottom sheet로 세션 목록 표시
- 항목 탭 시 해당 세션 선택
- `New session` 액션 제공

### 4. Resume behavior

- 선택된 세션이 있으면 connect 시 query parameter로 전달
- 세션 전환 시 기존 transcript를 해당 세션 턴 목록으로 교체
- 새 세션 선택 시 transcript를 비우고 이후 새 `session_ready`를 기다림

## Data Contract

### Session summary

예상 필드:

- `conversation_id`
- `title`
- `preview`
- `created_at`
- `updated_at`
- `turn_count`
- `domain`
- `is_active`

### Session detail

추가 필드:

- `turns[]`
  - `turn_id`
  - `role`
  - `text`
  - `is_final`
  - `status`
  - `created_at`

## Implementation Order

1. conversation store 추가
2. 세션 조회 API 추가
3. `ws_mobile` lazy binding + 복구 로직 추가
4. 최종 턴 저장 로직 연결
5. 모바일 session catalog service 추가
6. session list UI 추가
7. 세션 선택/신규 세션 UX 연결
8. 테스트 추가

## Test Plan

### Backend unit tests

- standalone weather 질문은 새 세션으로 분기
- follow-up 질문은 최근 관련 세션 복구
- explicit conversation 선택 시 정확한 세션 복구
- relevance score가 낮으면 새 세션 생성

### Integration checks

- 같은 세션 선택 후 재접속 시 후속 질문이 이전 맥락을 유지하는지
- 세션 목록 API가 최신 preview/updated_at을 반영하는지
- 새 세션 생성 후 목록에 즉시 나타나는지

### Client checks

- 세션 목록이 표시되는지
- 세션 선택 시 transcript가 바뀌는지
- 새 세션 선택 시 빈 상태로 시작하는지

## Risks

- 오디오 첫 턴은 텍스트처럼 정교하게 분기하기 어렵다.
- ADK 세션 객체 재사용 시 런타임 전제 조건이 있을 수 있다.
- 인메모리 저장소라 서버 재시작 시 카탈로그와 세션이 모두 사라진다.

## Follow-up after this phase

- `conversation_store` 인터페이스를 Firestore 저장소로 교체
- 세션 archive/pin/favorite 정책 추가
- 세션 title 요약을 모델 기반으로 개선
- 오디오 첫 턴 분기 정확도 개선
