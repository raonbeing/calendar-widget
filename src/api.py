import os
import sys
from datetime import datetime, date

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

SCOPES = ['https://www.googleapis.com/auth/calendar.events']


def _base_dir() -> str:
    # PyInstaller로 패키징된 경우 exe 위치, 아니면 프로젝트 루트
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


_SECRETS_DIR = os.path.join(_base_dir(), 'secrets')
os.makedirs(_SECRETS_DIR, exist_ok=True)

_MISSING_CREDS_MSG = """\
credentials.json 파일이 없습니다.

[설정 방법]
1. console.cloud.google.com 접속
2. API 및 서비스 → 사용자 인증 정보
3. OAuth 2.0 클라이언트 ID 만들기 (데스크톱 앱)
4. JSON 다운로드 후 파일명을 credentials.json으로 변경
5. 아래 폴더에 넣고 프로그램 재시작

""" + os.path.join(_base_dir(), 'secrets')


def get_service():
    token_path = os.path.join(_SECRETS_DIR, 'token.json')
    creds_path = os.path.join(_SECRETS_DIR, 'credentials.json')

    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(creds_path):
                raise FileNotFoundError(_MISSING_CREDS_MSG)
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, 'w', encoding='utf-8') as f:
            f.write(creds.to_json())

    return build('calendar', 'v3', credentials=creds)


def fetch_today_events() -> tuple[list, str | None]:
    if not GOOGLE_AVAILABLE:
        return [], '필수 패키지 미설치\npip install -r requirements.txt'

    try:
        service = get_service()
        today = date.today()
        time_min = datetime(today.year, today.month, today.day, 0, 0, 0).astimezone().isoformat()
        time_max = datetime(today.year, today.month, today.day, 23, 59, 59).astimezone().isoformat()

        result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime',
        ).execute()

        return result.get('items', []), None
    except FileNotFoundError as e:
        return [], str(e)
    except Exception as e:
        return [], f'오류: {e}'


def create_event(title: str, start_dt: datetime, end_dt: datetime):
    service = get_service()
    service.events().insert(
        calendarId='primary',
        body={
            'summary': title,
            'start': {'dateTime': start_dt.isoformat()},
            'end':   {'dateTime': end_dt.isoformat()},
        }
    ).execute()


def delete_event(event_id: str):
    service = get_service()
    service.events().delete(calendarId='primary', eventId=event_id).execute()
