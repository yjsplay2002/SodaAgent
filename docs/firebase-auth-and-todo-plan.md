# Firebase Auth And Todo Plan

## 목표 구조

향후 클라이언트는 Firebase Authentication 기반 Google 로그인을 사용한다.
서버는 클라이언트가 전달한 Firebase ID token을 검증하고, 검증 결과의 `uid`를
서버 내부 사용자 식별자의 기준으로 사용한다.

핵심 원칙:

- 클라이언트가 임의로 만든 `user_id`는 더 이상 신뢰하지 않는다.
- 서버의 정규 사용자 키는 Firebase Auth `uid` 하나로 통일한다.
- 사용자 프로필/대화/리마인더/투두 메타데이터는 Firestore에 저장한다.
- 오디오, 내보내기 파일 같은 바이너리는 Cloud Storage에 저장한다.
- WebSocket은 직접 `uid`를 path로 받지 않고, 인증 후 발급한 짧은 수명의 티켓으로 접속한다.

## 권장 인증 흐름

1. Flutter 앱이 Firebase 초기화 후 Google 로그인 수행
2. Firebase Auth ID token 획득
3. 서버 `POST /api/auth/session` 호출
4. 서버가 Firebase Admin SDK로 ID token 검증
5. 서버가 `uid` 기준으로 사용자 레코드 upsert
6. 서버가 짧은 TTL의 WebSocket ticket 발급
7. 클라이언트가 ticket으로 WebSocket 연결
8. 서버는 ticket에서 확인된 `uid`를 세션/저장소 키로 사용

## Firebase 저장소 역할

- Firebase Authentication
  - 로그인
  - 사용자 신원 검증
- Cloud Firestore
  - 사용자 프로필
  - 대화 메타데이터
  - 투두/리마인더/활동 이력
  - 디바이스 등록 정보
- Cloud Storage for Firebase
  - 음성 응답 파일
  - 문서 export 결과
  - 기타 대용량 첨부 파일

## 권장 Firestore 데이터 모델

### `users/{uid}`

- `email`
- `display_name`
- `photo_url`
- `auth_provider`
- `created_at`
- `last_login_at`
- `last_seen_at`

### `users/{uid}/devices/{device_id}`

- `platform`
- `app_version`
- `last_seen_at`
- `last_session_id`

### `users/{uid}/conversations/{conversation_id}`

- `title`
- `status`
- `created_at`
- `updated_at`
- `last_turn_at`

### `users/{uid}/conversations/{conversation_id}/turns/{turn_id}`

- `role`
- `text`
- `is_final`
- `tool_name`
- `tool_args`
- `audio_path`
- `created_at`

### `users/{uid}/todos/{todo_id}`

- `title`
- `details`
- `priority`
- `category`
- `status`
- `created_at`
- `updated_at`
- `last_activity_at`

### `users/{uid}/todos/{todo_id}/history/{history_id}`

- `action`
- `note`
- `from_status`
- `to_status`
- `created_at`

## 현재 단계의 임시 구현

Firebase 로그인과 Firestore 연동 전까지는 서버 로컬 파일 시스템에
사용자별 Markdown 문서 1개를 저장한다.

임시 저장 원칙:

- 파일 위치: `backend/data/user_memory/<safe_user_id>.md`
- 파일 단위: 사용자당 1개
- 문서 내용:
  - 사람이 읽는 요약 섹션
  - 서버가 읽고 쓰는 canonical JSON fenced block
- 이 Markdown 문서 안에 다음 데이터를 함께 저장:
  - todo 목록
  - todo별 상태
  - todo별 히스토리
  - 사용자 단위 activity log

이 구조는 나중에 Firestore로 옮기기 쉽게 다음 기준을 따른다.

- 사용자 키는 파일명에서 그대로 유지 가능
- todo 레코드는 문서형 구조를 유지
- history는 append-only event 형태 유지

## Todo 에이전트 설계

서버 에이전트에 `todo_agent`를 추가한다.

역할:

- 사용자의 todo 관련 요청 전담
- 새 todo 요청 시 우선순위와 카테고리 분류
- todo 조회, 검색, 상태 변경 처리
- todo 관련 이력 조회
- 각 상태 변경과 주요 조회 이벤트를 히스토리로 축적

지원 상태:

- `todo`
- `in_progress`
- `review`
- `done`

초기 구현 규칙:

- 우선순위: `high`, `medium`, `low`
- 카테고리: 규칙 기반 추론
- 상태 변경은 제한하지 않는다
  - 예: `done -> in_progress` 허용
- 조회형 요청도 필요한 경우 activity log에 남긴다

## Todo 도구 초안

- `add_todo`
- `list_todos`
- `search_todos`
- `get_todo`
- `update_todo_status`
- `get_todo_history`

## 마이그레이션 방향

임시 Markdown 저장소에서 Firestore로 전환할 때는 저장 계층만 교체하고,
툴 시그니처와 에이전트 동작은 최대한 유지한다.

권장 전환 순서:

1. Firebase Auth 도입
2. 서버 token 검증과 `uid` 기반 세션화
3. Markdown storage service 인터페이스 유지한 채 Firestore 구현 추가
4. todo/reminder/conversation 저장소를 Firestore로 이전
5. 오디오/첨부 파일을 Cloud Storage로 분리
