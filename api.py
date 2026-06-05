import os
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
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_SECRETS_DIR = os.path.join(_BASE_DIR, 'secrets')


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
                raise FileNotFoundError(
                    'credentials.json 파일이 없습니다.\n'
                    'Google Cloud Console에서 OAuth 클라이언트 ID를 만들고\n'
                    'credentials.json을 같은 폴더에 넣어주세요.'
                )
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
