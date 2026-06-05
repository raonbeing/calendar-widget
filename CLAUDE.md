# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

Google Calendar 일정을 Windows 바탕화면 위젯으로 표시하는 Python 프로그램.
오늘 일정 조회, 일정 추가, 투명도 조절 기능을 제공한다.

## 기술 스택

- Language: Python 3.13
- UI: tkinter (항상 위 표시, 투명 배경, 드래그 이동)
- API: Google Calendar API v3 (OAuth2 인증)

## 파일 구조 원칙

- 파일은 기능별로 분리한다 (UI / API / 설정 / 진입점 등)
- 새 기능 추가 시 기존 파일에 무조건 붙이지 말고 역할에 맞는 파일에 넣는다
- 파일별 상세 역할은 `STRUCTURE.txt` 에 별도 관리한다

## 개발 환경 설정

### 가상환경 (venv) — 항상 사용할 것

```powershell
# 최초 1회: 가상환경 생성 및 패키지 설치
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 이후 매 작업 시작 시
.venv\Scripts\activate

# 실행
python calendar_widget.py
```

> `.venv` 폴더는 `.gitignore`에 추가해 커밋하지 않는다.

## 자주 쓰는 명령어

```bash
# 테스트 실행
# npm test  또는  pytest

# 빌드
# npm run build
```

## Claude에게 주는 지침

### 코딩 스타일
- 함수명, 변수명은 영어로 작성
- 불필요한 주석은 달지 않기
- 기존 파일을 수정할 때는 Read 후 Edit 사용

### 하지 말아야 할 것
- `git push` 전에 반드시 확인 요청
- 파일 삭제 전에 반드시 확인 요청
- 테스트 없이 프로덕션 코드 변경 금지
- `credentials.json`, `token.json`, `.env` 등 개인정보·인증 파일은 절대 커밋하지 않는다
- 코드에 API 키, 비밀번호, 이메일 등 개인정보를 하드코딩하지 않는다

### 선호하는 방식
- 코드 변경 시 변경 이유 설명
- 큰 작업은 단계별로 나눠서 진행
- 에러 발생 시 원인 파악 후 수정

### 실수 관리 원칙
- Claude가 실수할 때마다 이 실수를 반복하지 않도록 CLAUDE.md를 업데이트한다
- 실수는 아래 "과거 실수 기록" 섹션에 추가한다

## 과거 실수 기록

### 여러 위치에 같은 값을 변경할 때 일관성 확인 누락
- `after(0, ...)` → `after(1000, ...)` 변경 시 `_do_delete`와 `_do_create` 두 곳 모두 수정했지만, 이후 사용자가 IDE에서 하나만 2000으로 바꿔 불일치 발생
- **교훈:** 같은 논리적 의미를 가진 값이 여러 곳에 있을 때, git push 전 diff를 반드시 확인하여 모든 위치의 값이 일관된지 검증한다

## 주의사항

<!-- 프로젝트 특이사항, 알려진 버그, 임시 해결책 등 -->
