# 프로젝트 파일 구조

Google Calendar 일정을 Windows 바탕화면 위젯으로 표시하는 Python 프로그램.

## 파일 역할

| 파일 | 역할 |
|------|------|
| `calendar_widget.py` | 진입점(main) — 실행 시 이 파일만 호출 |
| `src/ui.py` | tkinter UI 전체 (CalendarWidget 클래스, 이벤트 렌더링, 다이얼로그) |
| `src/api.py` | Google Calendar API 호출 (인증, 일정 조회/생성/삭제) |
| `src/config.py` | 사용자 설정 저장·로드 (투명도, 배경색, 강조색) |
| `secrets/` | git 제외 폴더. credentials.json, token.json, config.json 보관 |

## 원칙

- 기능별 파일 분리. 새 기능 추가 시 역할에 맞는 파일에 넣는다.
- `secrets/` 하위 파일은 절대 커밋 금지.
