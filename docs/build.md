# PyInstaller 빌드

PyInstaller로 단일 exe 패키징 지원.

## 경로 처리 (`_base_dir()`)

`src/api.py`와 `src/config.py`의 `_base_dir()` 함수가 경로 기준점을 결정한다.

```python
def _base_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)   # exe 실행 시
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 일반 실행 시
```

- **exe로 패키징된 경우:** `sys.executable` 기준 (exe 파일 위치)
- **일반 실행 시:** `__file__`에서 두 단계 위 (프로젝트 루트)

> exe로 실행할 때 `__file__`은 임시 압축 해제 경로를 가리켜 `secrets/` 폴더를 찾지 못하는 문제가 있었음.

## 빌드 관련 파일

- `.gitignore`에 `build/`, `dist/`, `*.spec` 추가됨 (커밋 제외)
- 시작 시 `secrets/` 디렉토리 없으면 자동 생성
- `credentials.json` 누락 시 상세 설정 가이드 메시지 표시
