# Google OAuth 인증 흐름

설정 다이얼로그에서 인증 상태 확인 및 `credentials.json` 가져오기 지원.

## 인증 상태 3단계

| 상태 | 조건 |
|------|------|
| ✗ 미설정 | `credentials.json` 없음 |
| △ 로그인 필요 | `credentials.json` 있음, `token.json` 없음 |
| ✓ 연결됨 | 둘 다 있음 |

## 새 credentials 가져오기 시 동작

1. 파일 피커로 새 `credentials.json` 선택
2. `secrets/credentials.json`으로 복사
3. 기존 `token.json` 자동 삭제
4. 다음 API 호출 시 재인증 진행

> 새 credentials와 기존 token이 함께 있으면 인증 오류 발생. 자동 삭제로 방지.

## 주의

- `secrets/` 하위 파일은 절대 git에 커밋하지 않는다.
