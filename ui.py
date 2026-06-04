import tkinter as tk
from tkinter import messagebox
import threading
from datetime import datetime, date

from api import fetch_today_events, create_event
from config import load_alpha, save_alpha

TRANSPARENT_COLOR = '#000001'
REFRESH_INTERVAL_MS = 30 * 60 * 1000

COLORS = {
    'bg_root':    TRANSPARENT_COLOR,
    'bg_widget':  '#1a1a2e',
    'bg_header':  '#16213e',
    'bg_card':    '#0f3460',
    'bg_allday':  '#2d1b69',
    'text_main':  '#e2e2e2',
    'text_sub':   '#a8a8b3',
    'text_time':  '#4cc9f0',
    'text_allday':'#f72585',
    'btn_refresh':'#0f3460',
    'btn_close':  '#c62a47',
}


def _parse_event_time(event: dict) -> tuple[str, bool]:
    raw = event['start'].get('dateTime') or event['start'].get('date', '')
    if 'T' in raw:
        dt = datetime.fromisoformat(raw).astimezone()
        return dt.strftime('%H:%M'), False
    return '종일', True


class CalendarWidget:
    def __init__(self):
        self.root = tk.Tk()
        self._drag_x = 0
        self._drag_y = 0
        self._alpha = load_alpha()
        self._setup_window()
        self._build_ui()
        self._load_calendar()
        self._schedule_refresh()

    # ──────────────────────────────────────────
    # 창 설정
    # ──────────────────────────────────────────

    def _setup_window(self):
        self.root.title('캘린더 위젯')
        self.root.overrideredirect(True)
        self.root.wm_attributes('-topmost', True)
        self.root.wm_attributes('-toolwindow', True)
        self.root.wm_attributes('-transparentcolor', TRANSPARENT_COLOR)
        self.root.wm_attributes('-alpha', self._alpha)
        self.root.configure(bg=TRANSPARENT_COLOR)

        sw = self.root.winfo_screenwidth()
        self.root.geometry(f'300x470+{sw - 320}+20')
        self.root.minsize(260, 200)

        self.root.bind('<Button-1>',  self._drag_start)
        self.root.bind('<B1-Motion>', self._drag_move)

    def _drag_start(self, e):
        self._drag_x = e.x
        self._drag_y = e.y

    def _drag_move(self, e):
        x = self.root.winfo_x() + e.x - self._drag_x
        y = self.root.winfo_y() + e.y - self._drag_y
        self.root.geometry(f'+{x}+{y}')

    # ──────────────────────────────────────────
    # UI 구성
    # ──────────────────────────────────────────

    def _build_ui(self):
        outer = tk.Frame(self.root, bg=COLORS['bg_widget'], bd=0)
        outer.pack(fill='both', expand=True, padx=4, pady=4)

        self._build_header(outer)
        self._build_events_area(outer)
        self._build_footer(outer)

    def _build_header(self, parent):
        today = date.today()
        weekdays = ['월', '화', '수', '목', '금', '토', '일']
        date_str = f"{today.strftime('%Y년 %m월 %d일')} ({weekdays[today.weekday()]})"

        hdr = tk.Frame(parent, bg=COLORS['bg_header'])
        hdr.pack(fill='x', padx=2, pady=(2, 0))

        tk.Label(
            hdr, text=f'  {date_str}',
            fg=COLORS['text_main'], bg=COLORS['bg_header'],
            font=('Malgun Gothic', 11, 'bold'), anchor='w', pady=8
        ).pack(fill='x')

        self.status_lbl = tk.Label(
            hdr, text='로딩 중...',
            fg=COLORS['text_sub'], bg=COLORS['bg_header'],
            font=('Malgun Gothic', 8), anchor='w', padx=6, pady=2
        )
        self.status_lbl.pack(fill='x')

    def _build_events_area(self, parent):
        container = tk.Frame(parent, bg=COLORS['bg_widget'])
        container.pack(fill='both', expand=True, padx=4, pady=4)

        canvas = tk.Canvas(container, bg=COLORS['bg_widget'], highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(container, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        self.events_frame = tk.Frame(canvas, bg=COLORS['bg_widget'])
        self._canvas_window = canvas.create_window((0, 0), window=self.events_frame, anchor='nw')

        self.events_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(self._canvas_window, width=e.width))
        canvas.bind('<MouseWheel>', lambda e: canvas.yview_scroll(-1 * (e.delta // 120), 'units'))

    def _build_footer(self, parent):
        footer = tk.Frame(parent, bg=COLORS['bg_widget'])
        footer.pack(fill='x', padx=4, pady=(0, 2))

        tk.Button(
            footer, text='새로고침', command=self._load_calendar,
            bg=COLORS['btn_refresh'], fg=COLORS['text_main'],
            font=('Malgun Gothic', 8), relief='flat', cursor='hand2',
            padx=10, pady=3, bd=0
        ).pack(side='left')

        tk.Button(
            footer, text='+ 일정 추가', command=self._open_add_dialog,
            bg='#1b6b3a', fg=COLORS['text_main'],
            font=('Malgun Gothic', 8), relief='flat', cursor='hand2',
            padx=10, pady=3, bd=0
        ).pack(side='left', padx=(4, 0))

        tk.Button(
            footer, text='✕', command=self.root.destroy,
            bg=COLORS['btn_close'], fg='white',
            font=('Malgun Gothic', 9, 'bold'), relief='flat', cursor='hand2',
            padx=8, pady=3, bd=0
        ).pack(side='right')

        # 투명도 슬라이더
        alpha_row = tk.Frame(parent, bg=COLORS['bg_widget'])
        alpha_row.pack(fill='x', padx=4, pady=(0, 4))

        tk.Label(
            alpha_row, text='투명도',
            fg=COLORS['text_sub'], bg=COLORS['bg_widget'],
            font=('Malgun Gothic', 7)
        ).pack(side='left')

        self._alpha_var = tk.IntVar(value=int(self._alpha * 100))
        tk.Scale(
            alpha_row,
            from_=20, to=100,
            orient='horizontal',
            variable=self._alpha_var,
            command=self._on_alpha_change,
            bg=COLORS['bg_widget'], fg=COLORS['text_sub'],
            troughcolor=COLORS['bg_card'],
            activebackground=COLORS['text_time'],
            highlightthickness=0, bd=0,
            sliderlength=12, length=180, width=8,
            showvalue=False,
        ).pack(side='left', padx=(4, 0))

        self._alpha_pct_lbl = tk.Label(
            alpha_row, text=f'{self._alpha_var.get()}%',
            fg=COLORS['text_sub'], bg=COLORS['bg_widget'],
            font=('Malgun Gothic', 7), width=4
        )
        self._alpha_pct_lbl.pack(side='left')

    def _on_alpha_change(self, val):
        alpha = int(val) / 100
        self.root.wm_attributes('-alpha', alpha)
        self._alpha_pct_lbl.config(text=f'{int(val)}%')
        save_alpha(alpha)

    # ──────────────────────────────────────────
    # 이벤트 렌더링
    # ──────────────────────────────────────────

    def _load_calendar(self):
        self.status_lbl.config(text='로딩 중...')
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        events, error = fetch_today_events()
        self.root.after(0, self._render, events, error)

    def _render(self, events: list, error: str | None):
        for w in self.events_frame.winfo_children():
            w.destroy()

        now = datetime.now().strftime('%H:%M')

        if error:
            self.status_lbl.config(text='오류 발생')
            self._add_message(error, COLORS['text_sub'])
            return

        self.status_lbl.config(text=f'업데이트: {now} · {len(events)}개 일정')

        if not events:
            self._add_message('오늘 일정이 없습니다 🎉', COLORS['text_sub'])
            return

        for event in events:
            self._add_event_card(event)

    def _add_message(self, text: str, color: str):
        tk.Label(
            self.events_frame, text=text,
            fg=color, bg=COLORS['bg_widget'],
            font=('Malgun Gothic', 9),
            wraplength=260, justify='left', pady=16
        ).pack(padx=8, anchor='w')

    def _add_event_card(self, event: dict):
        time_str, is_allday = _parse_event_time(event)
        summary  = event.get('summary', '(제목 없음)')
        location = event.get('location', '')

        card_bg    = COLORS['bg_allday'] if is_allday else COLORS['bg_card']
        time_color = COLORS['text_allday'] if is_allday else COLORS['text_time']

        card = tk.Frame(self.events_frame, bg=card_bg, padx=10, pady=6)
        card.pack(fill='x', pady=(0, 4), padx=2)

        top = tk.Frame(card, bg=card_bg)
        top.pack(fill='x')

        tk.Label(top, text=time_str, fg=time_color, bg=card_bg,
                 font=('Malgun Gothic', 9, 'bold')).pack(side='left', padx=(0, 8))
        tk.Label(top, text=summary, fg=COLORS['text_main'], bg=card_bg,
                 font=('Malgun Gothic', 10), anchor='w').pack(side='left', fill='x', expand=True)

        if location:
            tk.Label(card, text=f'📍 {location}', fg=COLORS['text_sub'], bg=card_bg,
                     font=('Malgun Gothic', 8), anchor='w',
                     wraplength=260, justify='left').pack(fill='x', pady=(2, 0))

    # ──────────────────────────────────────────
    # 일정 추가 다이얼로그
    # ──────────────────────────────────────────

    def _open_add_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title('일정 추가')
        dlg.configure(bg=COLORS['bg_widget'])
        dlg.resizable(False, False)
        dlg.wm_attributes('-topmost', True)
        dlg.geometry(f'280x260+{self.root.winfo_x() - 290}+{self.root.winfo_y()}')

        def row(label_text, default=''):
            f = tk.Frame(dlg, bg=COLORS['bg_widget'])
            f.pack(fill='x', padx=14, pady=4)
            tk.Label(f, text=label_text, fg=COLORS['text_sub'], bg=COLORS['bg_widget'],
                     font=('Malgun Gothic', 8), width=8, anchor='w').pack(side='left')
            entry = tk.Entry(f, bg=COLORS['bg_card'], fg=COLORS['text_main'],
                             insertbackground=COLORS['text_main'],
                             font=('Malgun Gothic', 10), relief='flat', bd=4)
            entry.insert(0, default)
            entry.pack(side='left', fill='x', expand=True)
            return entry

        tk.Label(dlg, text='일정 추가', fg=COLORS['text_main'], bg=COLORS['bg_header'],
                 font=('Malgun Gothic', 11, 'bold'), pady=8).pack(fill='x')

        today_str = date.today().strftime('%Y-%m-%d')
        e_title = row('제목')
        e_date  = row('날짜', today_str)
        e_start = row('시작 (HH:MM)', '09:00')
        e_end   = row('종료 (HH:MM)', '10:00')

        msg_lbl = tk.Label(dlg, text='', fg='#ff6b6b', bg=COLORS['bg_widget'],
                           font=('Malgun Gothic', 8))
        msg_lbl.pack()

        def submit():
            title     = e_title.get().strip()
            date_str  = e_date.get().strip()
            start_str = e_start.get().strip()
            end_str   = e_end.get().strip()

            if not title:
                msg_lbl.config(text='제목을 입력해주세요')
                return
            try:
                start_dt = datetime.strptime(f'{date_str} {start_str}', '%Y-%m-%d %H:%M').astimezone()
                end_dt   = datetime.strptime(f'{date_str} {end_str}',   '%Y-%m-%d %H:%M').astimezone()
            except ValueError:
                msg_lbl.config(text='날짜/시간 형식을 확인해주세요')
                return
            if end_dt <= start_dt:
                msg_lbl.config(text='종료 시간이 시작 시간보다 늦어야 합니다')
                return

            msg_lbl.config(text='추가 중...', fg=COLORS['text_sub'])
            dlg.update()
            threading.Thread(target=self._do_create, args=(dlg, title, start_dt, end_dt), daemon=True).start()

        btn_frame = tk.Frame(dlg, bg=COLORS['bg_widget'])
        btn_frame.pack(fill='x', padx=14, pady=8)

        tk.Button(btn_frame, text='추가', command=submit,
                  bg='#1b6b3a', fg='white', font=('Malgun Gothic', 9, 'bold'),
                  relief='flat', cursor='hand2', padx=14, pady=4, bd=0).pack(side='left')
        tk.Button(btn_frame, text='취소', command=dlg.destroy,
                  bg=COLORS['bg_card'], fg=COLORS['text_main'], font=('Malgun Gothic', 9),
                  relief='flat', cursor='hand2', padx=14, pady=4, bd=0).pack(side='left', padx=(6, 0))

    def _do_create(self, dlg, title: str, start_dt: datetime, end_dt: datetime):
        try:
            create_event(title, start_dt, end_dt)
            self.root.after(0, dlg.destroy)
            self.root.after(0, self._load_calendar)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror('오류', str(e)))

    # ──────────────────────────────────────────
    # 자동 갱신
    # ──────────────────────────────────────────

    def _schedule_refresh(self):
        self.root.after(REFRESH_INTERVAL_MS, self._auto_refresh)

    def _auto_refresh(self):
        self._load_calendar()
        self._schedule_refresh()

    def run(self):
        self.root.mainloop()
