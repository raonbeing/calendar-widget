import os
import shutil
import calendar
import tkinter as tk
from tkinter import messagebox, colorchooser, filedialog
import threading
from datetime import datetime, date, timedelta

from .api import fetch_events_for_date, create_event, delete_event, _SECRETS_DIR
from .config import load_settings, save_settings

TRANSPARENT_COLOR = '#000001'
REFRESH_INTERVAL_MS = 30 * 60 * 1000

LABEL_W   = 42   # 시간 레이블 열 너비
EARLY_END = 7    # 00~06시는 기본 숨김
TOGGLE_H  = 18   # 토글 바 높이

_FIXED_COLORS = {
    'bg_root':     TRANSPARENT_COLOR,
    'text_header': '#ffffff',
    'text_date':   '#7777aa',
    'text_time':   '#4cc9f0',
    'text_allday': '#f0c040',
    'text_main':   '#dddddd',
    'text_sub':    '#444455',
    'btn_bg':      '#1e1e2e',
    'btn_add':     '#1b4d2e',
    'btn_close':   '#c62a47',
}


def _build_colors(settings: dict) -> dict:
    c = dict(_FIXED_COLORS)
    c['bg_widget']  = settings.get('bg_widget',  '#111118')
    c['acc_event']  = settings.get('acc_event',  '#4cc9f0')
    c['acc_allday'] = settings.get('acc_allday', '#f0c040')
    c['sep']        = _darken(c['bg_widget'], 30)
    c['grid']       = _darken(c['bg_widget'], 20)
    c['evt_fill']   = _mix(c['bg_widget'], c['acc_event'],  0.25)
    c['evt_allday_fill'] = _mix(c['bg_widget'], c['acc_allday'], 0.25)
    return c


def _darken(hex_color: str, amount: int = 30) -> str:
    try:
        r, g, b = int(hex_color[1:3],16), int(hex_color[3:5],16), int(hex_color[5:7],16)
        return f'#{max(0,r-amount):02x}{max(0,g-amount):02x}{max(0,b-amount):02x}'
    except Exception:
        return '#2a2a3a'


def _mix(hex1: str, hex2: str, ratio: float) -> str:
    try:
        r1,g1,b1 = int(hex1[1:3],16),int(hex1[3:5],16),int(hex1[5:7],16)
        r2,g2,b2 = int(hex2[1:3],16),int(hex2[3:5],16),int(hex2[5:7],16)
        r = int(r1*(1-ratio) + r2*ratio)
        g = int(g1*(1-ratio) + g2*ratio)
        b = int(b1*(1-ratio) + b2*ratio)
        return f'#{r:02x}{g:02x}{b:02x}'
    except Exception:
        return hex1


class CalendarWidget:
    def __init__(self):
        self.root = tk.Tk()
        self._drag_x = 0
        self._drag_y = 0
        self._settings = load_settings()
        self._alpha = self._settings.get('alpha', 0.85)
        self._colors = _build_colors(self._settings)
        self._view_date: date = date.today()
        self._timed_events: list = []
        self._event_tags: dict = {}   # tag → event dict
        self._show_early: bool = False
        self._setup_window()
        self._build_ui()
        self._schedule_time_update()
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
        self.root.geometry(f'280x500+{sw - 300}+20')
        self.root.minsize(240, 300)

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
        self._outer = tk.Frame(self.root, bg=self._colors['bg_widget'], bd=0)
        self._outer.pack(fill='both', expand=True, padx=6, pady=6)
        self._build_header(self._outer)
        self._build_events_area(self._outer)
        self._build_footer(self._outer)

    def _rebuild_ui(self):
        self._colors = _build_colors(self._settings)
        self._outer.config(bg=self._colors['bg_widget'])
        for w in self._outer.winfo_children():
            w.destroy()
        self._build_header(self._outer)
        self._build_events_area(self._outer)
        self._build_footer(self._outer)
        self._load_calendar()

    def _format_date_str(self) -> str:
        weekdays = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
        d = self._view_date
        return f"{d.strftime('%Y.%m.%d')}  {weekdays[d.weekday()]}"

    def _header_date_color(self) -> str:
        if self._view_date == date.today():
            return '#e8e8ff'
        return '#4cc9f0'

    def _navigate_date(self, delta: int):
        self._view_date += timedelta(days=delta)
        if hasattr(self, '_date_lbl'):
            self._date_lbl.config(
                text=self._format_date_str(),
                fg=self._header_date_color()
            )
        self._load_calendar()

    def _open_date_picker(self):
        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)
        popup.wm_attributes('-topmost', True)
        popup.configure(bg=self._colors['bg_widget'])

        x = self.root.winfo_x() + 6
        y = self.root.winfo_y() + 46
        popup.geometry(f'210x190+{x}+{y}')

        tk.Frame(popup, bg=self._colors['sep'], height=1).pack(fill='x')

        frame = tk.Frame(popup, bg=self._colors['bg_widget'])
        frame.pack(fill='both', expand=True, padx=6, pady=6)

        view = [self._view_date.year, self._view_date.month]

        def build():
            for w in frame.winfo_children():
                w.destroy()

            yr, mo = view[0], view[1]

            nav_row = tk.Frame(frame, bg=self._colors['bg_widget'])
            nav_row.pack(fill='x', pady=(0, 6))

            tk.Button(nav_row, text='‹', command=lambda: (view.__setitem__(1, view[1]-1) if view[1]>1 else (view.__setitem__(0,view[0]-1), view.__setitem__(1,12))) or build(),
                      bg=self._colors['bg_widget'], fg=self._colors['text_time'],
                      font=('Consolas', 11, 'bold'), relief='flat', bd=0, cursor='hand2',
                      padx=4).pack(side='left')

            tk.Button(nav_row, text='›', command=lambda: (view.__setitem__(1, view[1]+1) if view[1]<12 else (view.__setitem__(0,view[0]+1), view.__setitem__(1,1))) or build(),
                      bg=self._colors['bg_widget'], fg=self._colors['text_time'],
                      font=('Consolas', 11, 'bold'), relief='flat', bd=0, cursor='hand2',
                      padx=4).pack(side='right')

            tk.Label(nav_row, text=f'{yr}.{mo:02d}',
                     fg=self._colors['text_header'], bg=self._colors['bg_widget'],
                     font=('Consolas', 9, 'bold')).pack(expand=True)

            grid = tk.Frame(frame, bg=self._colors['bg_widget'])
            grid.pack()

            for col, label in enumerate(['Mo','Tu','We','Th','Fr','Sa','Su']):
                fg = '#ff8888' if col >= 5 else self._colors['text_sub']
                tk.Label(grid, text=label, fg=fg, bg=self._colors['bg_widget'],
                         font=('Consolas', 7), width=3, anchor='center').grid(row=0, column=col, pady=(0,2))

            today = date.today()
            for week_i, week in enumerate(calendar.monthcalendar(yr, mo)):
                for day_i, day in enumerate(week):
                    if day == 0:
                        tk.Label(grid, text='', bg=self._colors['bg_widget'], width=3).grid(row=week_i+1, column=day_i)
                        continue
                    d = date(yr, mo, day)
                    if d == self._view_date:
                        bg, fg = self._colors['acc_event'], self._colors['bg_widget']
                    elif d == today:
                        bg, fg = self._colors['bg_widget'], '#ff4444'
                    else:
                        bg = self._colors['bg_widget']
                        fg = '#ff9999' if day_i >= 5 else self._colors['text_main']
                    tk.Button(
                        grid, text=str(day), bg=bg, fg=fg,
                        font=('Consolas', 7), relief='flat', bd=0, cursor='hand2',
                        width=3, pady=1,
                        command=lambda d=d: select(d)
                    ).grid(row=week_i+1, column=day_i)

        def select(d: date):
            self._view_date = d
            if hasattr(self, '_date_lbl'):
                self._date_lbl.config(text=self._format_date_str(), fg=self._header_date_color())
            self._load_calendar()
            popup.destroy()

        build()
        popup.bind('<Escape>', lambda _: popup.destroy())
        popup.bind('<FocusOut>', lambda _: popup.destroy())
        popup.focus_set()

    def _build_header(self, parent):
        hdr = tk.Frame(parent, bg=self._colors['bg_widget'])
        hdr.pack(fill='x', padx=8, pady=(8, 4))

        nav = tk.Frame(hdr, bg=self._colors['bg_widget'])
        nav.pack(fill='x')

        tk.Button(
            nav, text='‹', command=lambda: self._navigate_date(-1),
            bg=self._colors['bg_widget'], fg=self._colors['text_time'],
            font=('Consolas', 12, 'bold'), relief='flat', cursor='hand2',
            padx=6, pady=0, bd=0
        ).pack(side='left')

        tk.Button(
            nav, text='›', command=lambda: self._navigate_date(1),
            bg=self._colors['bg_widget'], fg=self._colors['text_time'],
            font=('Consolas', 12, 'bold'), relief='flat', cursor='hand2',
            padx=6, pady=0, bd=0
        ).pack(side='right')

        self._date_lbl = tk.Label(
            nav, text=self._format_date_str(),
            fg=self._header_date_color(), bg=self._colors['bg_widget'],
            font=('Consolas', 9, 'bold'), anchor='center', cursor='hand2'
        )
        self._date_lbl.pack(fill='x', expand=True)
        self._date_lbl.bind('<Button-1>', lambda e: (self._open_date_picker(), 'break'))

        self.status_lbl = tk.Label(
            hdr, text='',
            fg=self._colors['text_sub'], bg=self._colors['bg_widget'],
            font=('Consolas', 7), anchor='center'
        )
        self.status_lbl.pack(fill='x', pady=(1, 0))

        tk.Frame(parent, bg=self._colors['sep'], height=1).pack(fill='x', padx=8, pady=(6, 0))

    def _build_events_area(self, parent):
        # 종일 이벤트 영역 (고정)
        self._allday_frame = tk.Frame(parent, bg=self._colors['bg_widget'])
        self._allday_frame.pack(fill='x')

        # 타임라인 캔버스 (스크롤)
        container = tk.Frame(parent, bg=self._colors['bg_widget'])
        container.pack(fill='both', expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self._canvas = tk.Canvas(
            container, bg=self._colors['bg_widget'],
            highlightthickness=0, bd=0
        )
        scrollbar = tk.Scrollbar(container, orient='vertical', command=self._canvas.yview)
        self._canvas.grid(row=0, column=0, sticky='nsew')

        def _autoscroll(first, last):
            if float(first) <= 0.0 and float(last) >= 1.0:
                scrollbar.grid_remove()
            else:
                scrollbar.grid(row=0, column=1, sticky='ns')
            scrollbar.set(first, last)

        self._canvas.configure(yscrollcommand=_autoscroll)

        self._canvas.bind('<MouseWheel>',
            lambda e: self._canvas.yview_scroll(-1 * (e.delta // 120), 'units'))
        self._canvas.bind('<Configure>', lambda _: self._on_canvas_resize())
        self._canvas.bind('<Button-1>',        self._drag_select_start)
        self._canvas.bind('<B1-Motion>',       self._drag_select_move)
        self._canvas.bind('<ButtonRelease-1>', self._drag_select_end)
        self._drag_start_y: float | None = None

    def _build_footer(self, parent):
        tk.Frame(parent, bg=self._colors['sep'], height=1).pack(fill='x', padx=8, pady=(0, 6))

        btn_row = tk.Frame(parent, bg=self._colors['bg_widget'])
        btn_row.pack(fill='x', padx=8, pady=(0, 6))

        tk.Button(
            btn_row, text='↺', command=self._load_calendar,
            bg=self._colors['btn_bg'], fg=self._colors['text_time'],
            font=('Consolas', 11, 'bold'), relief='flat', cursor='hand2',
            padx=8, pady=2, bd=0
        ).pack(side='left')

        tk.Button(
            btn_row, text='+', command=self._open_add_dialog,
            bg=self._colors['btn_bg'], fg='#55cc88',
            font=('Consolas', 13, 'bold'), relief='flat', cursor='hand2',
            padx=8, pady=2, bd=0
        ).pack(side='left', padx=(4, 0))

        tk.Button(
            btn_row, text='⚙', command=self._open_settings_dialog,
            bg=self._colors['btn_bg'], fg=self._colors['text_date'],
            font=('Consolas', 10), relief='flat', cursor='hand2',
            padx=8, pady=2, bd=0
        ).pack(side='left', padx=(4, 0))

        tk.Button(
            btn_row, text='✕', command=self.root.destroy,
            bg=self._colors['btn_close'], fg='white',
            font=('Consolas', 9, 'bold'), relief='flat', cursor='hand2',
            padx=8, pady=2, bd=0
        ).pack(side='right')

    # ──────────────────────────────────────────
    # 캘린더 로드 & 렌더
    # ──────────────────────────────────────────

    def _load_calendar(self):
        self.status_lbl.config(text='loading...')
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        target = self._view_date
        events, error = fetch_events_for_date(target)
        self.root.after(0, self._render, events, error)

    def _render(self, events: list, error: str | None):
        # 종일 이벤트 영역 초기화
        for w in self._allday_frame.winfo_children():
            w.destroy()

        now = datetime.now().strftime('%H:%M')

        if error:
            self.status_lbl.config(text='error')
            self._canvas.delete('all')
            self._canvas.create_text(
                10, 20, text=error,
                anchor='nw', fill=self._colors['text_sub'],
                font=('Consolas', 8)
            )
            return

        allday = [e for e in events if 'T' not in (e['start'].get('dateTime') or '')]
        timed  = [e for e in events if 'T' in     (e['start'].get('dateTime') or '')]

        self.status_lbl.config(text=f'updated {now}  ·  {len(events)} events')
        self._timed_events = timed

        # 종일 이벤트 렌더
        for ev in allday:
            tk.Label(
                self._allday_frame,
                text=f'● {ev.get("summary", "")}',
                fg=self._colors['acc_allday'], bg=self._colors['bg_widget'],
                font=('Malgun Gothic', 8), anchor='w', padx=10, pady=2
            ).pack(fill='x')

        if allday:
            tk.Frame(self._allday_frame, bg=self._colors['sep'], height=1).pack(
                fill='x', padx=8, pady=(2, 0)
            )

        # 타임라인 렌더
        self._draw_timeline()

    # ──────────────────────────────────────────
    # 타임라인 그리기
    # ──────────────────────────────────────────

    def _on_canvas_resize(self):
        if self._timed_events is not None:
            self._draw_timeline()

    def _draw_timeline(self):
        canvas = self._canvas
        canvas.delete('all')
        self._event_tags.clear()

        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        if cw <= 1 or ch <= 1:
            return

        show_early = self._show_early
        if show_early:
            start_h = 0
            body_y  = 0
            body_h  = ch
        else:
            start_h = EARLY_END
            body_y  = TOGGLE_H
            body_h  = ch - TOGGLE_H

        px = body_h / (24 - start_h)
        self._px_per_hr  = px
        self._start_hour = start_h
        self._body_y     = body_y
        canvas.configure(scrollregion=(0, 0, cw, ch))

        # ── 토글 바 ──
        if not show_early:
            hidden = [
                e for e in self._timed_events
                if 'T' in e['start'].get('dateTime', '') and
                   datetime.fromisoformat(e['start']['dateTime']).astimezone().hour < EARLY_END
            ]
            badge = f'  ({len(hidden)}개 일정)' if hidden else ''
            canvas.create_rectangle(
                0, 0, cw, TOGGLE_H,
                fill=self._colors['btn_bg'], outline='', tags='toggle'
            )
            canvas.create_text(
                LABEL_W + 4, TOGGLE_H // 2,
                text=f'▶  00 – 06{badge}',
                anchor='w', fill=self._colors['text_sub'],
                font=('Consolas', 7), tags='toggle'
            )
            canvas.tag_bind('toggle', '<Button-1>', lambda _: self._toggle_early())
        else:
            y07 = (7 - start_h) * px   # 07:00 라인 y 좌표
            canvas.create_line(
                LABEL_W, y07, cw, y07,
                fill=self._colors['acc_allday'], width=1, dash=(3, 3), tags='toggle'
            )
            canvas.create_text(
                LABEL_W + 4, y07 - 7,
                text='▲ 접기',
                anchor='w', fill=self._colors['acc_allday'],
                font=('Consolas', 7), tags='toggle'
            )
            canvas.tag_bind('toggle', '<Button-1>', lambda _: self._toggle_early())

        # ── 시간 그리드 ──
        for h in range(start_h, 25):
            y = body_y + (h - start_h) * px
            canvas.create_line(LABEL_W, y, cw, y, fill=self._colors['grid'], width=1)
            if h < 24:
                canvas.create_text(
                    LABEL_W - 4, y + 2,
                    text=f'{h:02d}', anchor='ne',
                    fill=self._colors['text_sub'],
                    font=('Consolas', 7)
                )

        # ── 이벤트 블록 ──
        start_min = start_h * 60
        for i, event in enumerate(self._timed_events):
            raw_s = event['start'].get('dateTime', '')
            raw_e = event['end'].get('dateTime', '')
            if not raw_s or not raw_e:
                continue

            s = datetime.fromisoformat(raw_s).astimezone()
            e = datetime.fromisoformat(raw_e).astimezone()

            s_min = s.hour * 60 + s.minute
            e_min = e.hour * 60 + e.minute

            if e_min <= start_min:   # 표시 범위 이전에 끝나는 이벤트는 숨김
                continue

            y1 = body_y + (max(s_min, start_min) - start_min) * px / 60
            y2 = max(y1 + 14, body_y + (e_min - start_min) * px / 60)

            tag = f'evt_{i}'
            self._event_tags[tag] = event

            canvas.create_rectangle(
                LABEL_W + 2, y1 + 1, cw - 2, y2 - 1,
                fill=self._colors['evt_fill'],
                outline=self._colors['acc_event'],
                width=1, tags=(tag,)
            )
            canvas.create_text(
                LABEL_W + 7, y1 + 4,
                text=event.get('summary', ''),
                anchor='nw', fill=self._colors['text_main'],
                font=('Malgun Gothic', 8, 'bold'), tags=(tag,)
            )
            if y2 - y1 > 24:
                canvas.create_text(
                    LABEL_W + 7, y1 + 16,
                    text=f'{s.strftime("%H:%M")} – {e.strftime("%H:%M")}',
                    anchor='nw', fill=self._colors['text_date'],
                    font=('Consolas', 7), tags=(tag,)
                )

            canvas.tag_bind(tag, '<Button-3>', lambda e, t=tag: self._show_context_menu(e, t))

        self._draw_now_line()

    def _y_to_time(self, y: float) -> tuple[int, int]:
        body_y = getattr(self, '_body_y', TOGGLE_H)
        px     = getattr(self, '_px_per_hr', 15)
        start_h = getattr(self, '_start_hour', EARLY_END)
        total_min = int((y - body_y) / px * 60) + start_h * 60
        total_min = round(total_min / 15) * 15
        total_min = max(0, min(23 * 60 + 45, total_min))
        return total_min // 60, total_min % 60

    def _drag_select_start(self, e):
        body_y = getattr(self, '_body_y', TOGGLE_H)
        if e.y < body_y:
            self._drag_start_y = None
            return 'break'
        self._drag_start_y = e.y
        return 'break'

    def _drag_select_move(self, e):
        if self._drag_start_y is None:
            return 'break'
        self._canvas.delete('drag_select')
        y1 = min(self._drag_start_y, e.y)
        y2 = max(self._drag_start_y, e.y)
        cw = self._canvas.winfo_width()
        self._canvas.create_rectangle(
            LABEL_W + 2, y1, cw - 2, y2,
            fill=self._colors['acc_event'], outline='',
            stipple='gray50', tags='drag_select'
        )
        h1, m1 = self._y_to_time(y1)
        h2, m2 = self._y_to_time(y2)
        self._canvas.delete('drag_label')
        self._canvas.create_text(
            LABEL_W + 6, y1 + 3,
            text=f'{h1:02d}:{m1:02d}–{h2:02d}:{m2:02d}',
            anchor='nw', fill='white', font=('Consolas', 7), tags='drag_label'
        )
        return 'break'

    def _drag_select_end(self, e):
        if self._drag_start_y is None:
            return 'break'
        y1 = min(self._drag_start_y, e.y)
        y2 = max(self._drag_start_y, e.y)
        self._canvas.delete('drag_select')
        self._canvas.delete('drag_label')
        self._drag_start_y = None
        if y2 - y1 < 8:
            return 'break'
        h1, m1 = self._y_to_time(y1)
        h2, m2 = self._y_to_time(y2)
        if (h1, m1) == (h2, m2):
            m2 = m1 + 30
            if m2 >= 60:
                h2 += 1
                m2 -= 60
        self._open_quick_add_dialog(h1, m1, h2, m2)
        return 'break'

    def _open_quick_add_dialog(self, start_h: int, start_m: int, end_h: int, end_m: int):
        dlg = tk.Toplevel(self.root)
        dlg.configure(bg=self._colors['bg_widget'])
        dlg.resizable(False, False)
        dlg.wm_attributes('-topmost', True)
        dlg.overrideredirect(True)
        dlg.geometry(f'210x110+{self.root.winfo_x() - 220}+{self.root.winfo_y() + 80}')

        def entry_widget(parent, default, width=7):
            e = tk.Entry(
                parent, bg=self._colors['btn_bg'], fg=self._colors['text_main'],
                insertbackground=self._colors['text_main'],
                font=('Consolas', 9), relief='flat', bd=3, width=width, justify='center'
            )
            e.insert(0, default)
            return e

        # X 버튼
        tk.Button(
            dlg, text='✕', command=dlg.destroy,
            bg=self._colors['bg_widget'], fg=self._colors['text_sub'],
            font=('Consolas', 8), relief='flat', bd=0, cursor='hand2'
        ).place(relx=1.0, x=-4, y=4, anchor='ne')

        # 시간 행
        time_row = tk.Frame(dlg, bg=self._colors['bg_widget'])
        time_row.pack(fill='x', padx=8, pady=(10, 4))
        tk.Label(time_row, text='시간', fg=self._colors['text_sub'],
                 bg=self._colors['bg_widget'], font=('Consolas', 7), width=4, anchor='w').pack(side='left')
        e_start = entry_widget(time_row, f'{start_h:02d}:{start_m:02d}')
        e_start.pack(side='left')
        tk.Label(time_row, text='–', fg=self._colors['text_sub'],
                 bg=self._colors['bg_widget'], font=('Consolas', 8)).pack(side='left', padx=2)
        e_end = entry_widget(time_row, f'{end_h:02d}:{end_m:02d}')
        e_end.pack(side='left')

        # 제목 행
        title_row = tk.Frame(dlg, bg=self._colors['bg_widget'])
        title_row.pack(fill='x', padx=8, pady=(0, 4))
        tk.Label(title_row, text='제목', fg=self._colors['text_sub'],
                 bg=self._colors['bg_widget'], font=('Consolas', 7), width=4, anchor='w').pack(side='left')
        e_title = entry_widget(title_row, '', width=16)
        e_title.pack(side='left', fill='x', expand=True)
        e_title.focus_set()

        # 버튼 행
        btn_row = tk.Frame(dlg, bg=self._colors['bg_widget'])
        btn_row.pack(anchor='e', padx=8, pady=(0, 8))
        tk.Button(
            btn_row, text='추가', command=lambda: submit(),
            bg=self._colors['btn_add'], fg='#55cc88',
            font=('Consolas', 8, 'bold'), relief='flat', cursor='hand2',
            padx=10, pady=2, bd=0
        ).pack(side='left')
        tk.Button(
            btn_row, text='취소', command=dlg.destroy,
            bg=self._colors['btn_bg'], fg=self._colors['text_sub'],
            font=('Consolas', 8), relief='flat', cursor='hand2',
            padx=10, pady=2, bd=0
        ).pack(side='left', padx=(4, 0))

        target_date = self._view_date

        def submit(e=None):
            title = e_title.get().strip()
            if not title:
                e_title.focus_set()
                return
            try:
                sh, sm = [int(x) for x in e_start.get().split(':')]
                eh, em = [int(x) for x in e_end.get().split(':')]
            except ValueError:
                return
            dlg.destroy()
            start_dt = datetime(target_date.year, target_date.month, target_date.day, sh, sm).astimezone()
            end_dt   = datetime(target_date.year, target_date.month, target_date.day, eh, em).astimezone()
            self.status_lbl.config(text='추가 중...')
            threading.Thread(
                target=self._do_create, args=(None, title, start_dt, end_dt), daemon=True
            ).start()

        e_title.bind('<Return>', submit)
        e_start.bind('<Return>', lambda e: e_end.focus_set())
        e_end.bind('<Return>',   lambda e: e_title.focus_set())
        dlg.bind('<Escape>', lambda e: dlg.destroy())

    def _toggle_early(self):
        self._show_early = not self._show_early
        self._draw_timeline()

    def _draw_now_line(self):
        if not hasattr(self, '_canvas') or not self._canvas.winfo_exists():
            return
        canvas = self._canvas
        canvas.delete('now_line')

        if self._view_date != date.today():
            return

        now     = datetime.now()
        px      = getattr(self, '_px_per_hr', 15)
        start_h = getattr(self, '_start_hour', EARLY_END)
        body_y  = getattr(self, '_body_y', TOGGLE_H)

        if now.hour < start_h:
            return   # 현재 시각이 숨겨진 범위

        y  = body_y + (now.hour * 60 + now.minute - start_h * 60) * px / 60
        cw = canvas.winfo_width()
        if cw <= 1:
            return

        canvas.create_oval(
            LABEL_W - 4, y - 4, LABEL_W + 4, y + 4,
            fill='#ff4444', outline='', tags='now_line'
        )
        canvas.create_line(
            LABEL_W, y, cw, y,
            fill='#ff4444', width=1, tags='now_line'
        )

    def _schedule_time_update(self):
        self._draw_now_line()
        self.root.after(60_000, self._schedule_time_update)

    def _show_context_menu(self, e, tag: str):
        event = self._event_tags.get(tag)
        if not event:
            return
        menu = tk.Menu(self._canvas, tearoff=0)
        menu.configure(
            bg=self._colors['btn_bg'], fg=self._colors['text_main'],
            activebackground=self._colors['btn_close'], activeforeground='white',
            font=('Consolas', 8), bd=0, relief='flat'
        )
        event_id = event.get('id', '')
        menu.add_command(label='삭제', command=lambda: self._start_delete(event_id))
        menu.tk_popup(e.x_root, e.y_root)

    def _start_delete(self, event_id: str):
        if not event_id:
            return
        self.status_lbl.config(text='삭제 중...')
        threading.Thread(target=self._do_delete, args=(event_id,), daemon=True).start()

    def _do_delete(self, event_id: str):
        try:
            delete_event(event_id)
            self.root.after(2000, self._load_calendar)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror('오류', str(e)))

    # ──────────────────────────────────────────
    # 설정 다이얼로그
    # ──────────────────────────────────────────

    def _open_settings_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title('설정')
        dlg.configure(bg=self._colors['bg_widget'])
        dlg.resizable(False, False)
        dlg.wm_attributes('-topmost', True)
        dlg.geometry(f'240x380+{self.root.winfo_x() - 250}+{self.root.winfo_y()}')

        tk.Label(
            dlg, text='S E T T I N G S',
            fg=self._colors['text_header'], bg=self._colors['bg_widget'],
            font=('Consolas', 10, 'bold'), pady=8
        ).pack(fill='x')
        tk.Frame(dlg, bg=self._colors['sep'], height=1).pack(fill='x', padx=8)

        # 투명도
        af = tk.Frame(dlg, bg=self._colors['bg_widget'])
        af.pack(fill='x', padx=14, pady=(10, 4))
        tk.Label(af, text='투명도', fg=self._colors['text_sub'],
                 bg=self._colors['bg_widget'], font=('Consolas', 8),
                 width=10, anchor='w').pack(side='left')
        alpha_entry = tk.Entry(
            af, bg=self._colors['btn_bg'], fg=self._colors['text_main'],
            insertbackground=self._colors['text_main'],
            font=('Consolas', 9), relief='flat', bd=3, width=4, justify='center'
        )
        alpha_entry.insert(0, str(int(self._alpha * 100)))
        alpha_entry.pack(side='left')
        tk.Label(af, text='%  (20~100)', fg=self._colors['text_sub'],
                 bg=self._colors['bg_widget'], font=('Consolas', 7)).pack(side='left', padx=(4,0))

        tk.Frame(dlg, bg=self._colors['sep'], height=1).pack(fill='x', padx=8, pady=(8, 4))

        # Google 연동
        creds_path = os.path.join(_SECRETS_DIR, 'credentials.json')
        token_path = os.path.join(_SECRETS_DIR, 'token.json')

        def _auth_status():
            if os.path.exists(token_path):
                return '✓ 연결됨', '#55cc88'
            if os.path.exists(creds_path):
                return '△ 로그인 필요', '#f0c040'
            return '✗ 미설정', '#ff6b6b'

        gf = tk.Frame(dlg, bg=self._colors['bg_widget'])
        gf.pack(fill='x', padx=14, pady=(0, 4))

        tk.Label(gf, text='Google',
                 fg=self._colors['text_sub'], bg=self._colors['bg_widget'],
                 font=('Consolas', 8), width=10, anchor='w').pack(side='left')

        s_text, s_color = _auth_status()
        status_lbl = tk.Label(gf, text=s_text, fg=s_color,
                              bg=self._colors['bg_widget'], font=('Consolas', 8))
        status_lbl.pack(side='left')

        def import_credentials():
            path = filedialog.askopenfilename(
                parent=dlg,
                title='credentials.json 선택',
                filetypes=[('JSON 파일', '*.json'), ('모든 파일', '*.*')]
            )
            if not path:
                return
            try:
                shutil.copy(path, creds_path)
                if os.path.exists(token_path):
                    os.remove(token_path)
                status_lbl.config(text='△ 로그인 필요', fg='#f0c040')
            except Exception as e:
                messagebox.showerror('오류', str(e), parent=dlg)

        tk.Button(dlg, text='credentials.json 불러오기',
                  command=import_credentials,
                  bg=self._colors['btn_bg'], fg=self._colors['text_date'],
                  font=('Consolas', 8), relief='flat', cursor='hand2',
                  padx=8, pady=3, bd=0).pack(anchor='w', padx=14, pady=(2, 4))

        tk.Frame(dlg, bg=self._colors['sep'], height=1).pack(fill='x', padx=8, pady=(0, 4))

        # 색상
        pending = {
            'bg_widget':  self._colors['bg_widget'],
            'acc_event':  self._colors['acc_event'],
            'acc_allday': self._colors['acc_allday'],
        }

        def color_row(label, key):
            f = tk.Frame(dlg, bg=self._colors['bg_widget'])
            f.pack(fill='x', padx=14, pady=4)
            tk.Label(f, text=label, fg=self._colors['text_sub'],
                     bg=self._colors['bg_widget'], font=('Consolas', 8),
                     width=10, anchor='w').pack(side='left')
            swatch = tk.Frame(f, bg=pending[key], width=26, height=16, cursor='hand2')
            swatch.pack(side='left')
            swatch.pack_propagate(False)
            hex_lbl = tk.Label(f, text=pending[key], fg=self._colors['text_date'],
                               bg=self._colors['bg_widget'], font=('Consolas', 8))
            hex_lbl.pack(side='left', padx=(6, 0))

            def pick(sw=swatch, hl=hex_lbl, k=key):
                result = colorchooser.askcolor(color=pending[k], parent=dlg, title=label)
                if result[1]:
                    pending[k] = result[1]
                    sw.config(bg=result[1])
                    hl.config(text=result[1])

            swatch.bind('<Button-1>', lambda _, p=pick: p())

        color_row('배경 색', 'bg_widget')
        color_row('이벤트 색', 'acc_event')
        color_row('종일 색', 'acc_allday')

        tk.Frame(dlg, bg=self._colors['sep'], height=1).pack(fill='x', padx=8, pady=(8, 6))

        btn_frame = tk.Frame(dlg, bg=self._colors['bg_widget'])
        btn_frame.pack(fill='x', padx=14, pady=(0, 10))

        def save():
            try:
                val = max(20, min(100, int(alpha_entry.get())))
            except ValueError:
                val = int(self._alpha * 100)
            self._alpha = val / 100
            self.root.wm_attributes('-alpha', self._alpha)

            self._settings.update({
                'alpha':     round(self._alpha, 2),
                'bg_widget': pending['bg_widget'],
                'acc_event': pending['acc_event'],
                'acc_allday': pending['acc_allday'],
            })
            save_settings(self._settings)
            dlg.destroy()
            self._rebuild_ui()

        tk.Button(btn_frame, text='저장', command=save,
                  bg=self._colors['btn_add'], fg='#55cc88',
                  font=('Consolas', 9, 'bold'), relief='flat', cursor='hand2',
                  padx=14, pady=4, bd=0).pack(side='left')
        tk.Button(btn_frame, text='취소', command=dlg.destroy,
                  bg=self._colors['btn_bg'], fg=self._colors['text_sub'],
                  font=('Consolas', 9), relief='flat', cursor='hand2',
                  padx=14, pady=4, bd=0).pack(side='left', padx=(6, 0))

    # ──────────────────────────────────────────
    # 일정 추가 다이얼로그
    # ──────────────────────────────────────────

    def _open_add_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title('일정 추가')
        dlg.configure(bg=self._colors['bg_widget'])
        dlg.resizable(False, False)
        dlg.wm_attributes('-topmost', True)
        dlg.geometry(f'260x250+{self.root.winfo_x() - 270}+{self.root.winfo_y()}')

        tk.Label(dlg, text='A D D  E V E N T',
                 fg=self._colors['text_header'], bg=self._colors['bg_widget'],
                 font=('Consolas', 10, 'bold'), pady=10).pack(fill='x')
        tk.Frame(dlg, bg=self._colors['sep'], height=1).pack(fill='x', padx=8, pady=(0, 8))

        def row(label_text, default=''):
            f = tk.Frame(dlg, bg=self._colors['bg_widget'])
            f.pack(fill='x', padx=12, pady=3)
            tk.Label(f, text=label_text, fg=self._colors['text_sub'],
                     bg=self._colors['bg_widget'], font=('Consolas', 8),
                     width=7, anchor='w').pack(side='left')
            entry = tk.Entry(f, bg=self._colors['btn_bg'], fg=self._colors['text_main'],
                             insertbackground=self._colors['text_main'],
                             font=('Consolas', 9), relief='flat', bd=4)
            entry.insert(0, default)
            entry.pack(side='left', fill='x', expand=True)
            return entry

        today_str = self._view_date.strftime('%Y-%m-%d')
        e_title = row('title')
        e_date  = row('date', today_str)
        e_start = row('start', '09:00')
        e_end   = row('end', '10:00')

        msg_lbl = tk.Label(dlg, text='', fg='#ff6b6b', bg=self._colors['bg_widget'],
                           font=('Consolas', 7))
        msg_lbl.pack(pady=(4, 0))

        def submit():
            title     = e_title.get().strip()
            date_str  = e_date.get().strip()
            start_str = e_start.get().strip()
            end_str   = e_end.get().strip()
            if not title:
                msg_lbl.config(text='title required')
                return
            try:
                start_dt = datetime.strptime(f'{date_str} {start_str}', '%Y-%m-%d %H:%M').astimezone()
                end_dt   = datetime.strptime(f'{date_str} {end_str}',   '%Y-%m-%d %H:%M').astimezone()
            except ValueError:
                msg_lbl.config(text='invalid date / time format')
                return
            if end_dt <= start_dt:
                msg_lbl.config(text='end must be after start')
                return
            msg_lbl.config(text='adding...', fg=self._colors['text_sub'])
            dlg.update()
            threading.Thread(target=self._do_create,
                             args=(dlg, title, start_dt, end_dt), daemon=True).start()

        tk.Frame(dlg, bg=self._colors['sep'], height=1).pack(fill='x', padx=8, pady=(6, 6))

        bf = tk.Frame(dlg, bg=self._colors['bg_widget'])
        bf.pack(fill='x', padx=12, pady=(0, 10))
        tk.Button(bf, text='ADD', command=submit,
                  bg=self._colors['btn_add'], fg='#55cc88',
                  font=('Consolas', 9, 'bold'), relief='flat', cursor='hand2',
                  padx=14, pady=4, bd=0).pack(side='left')
        tk.Button(bf, text='CANCEL', command=dlg.destroy,
                  bg=self._colors['btn_bg'], fg=self._colors['text_sub'],
                  font=('Consolas', 9), relief='flat', cursor='hand2',
                  padx=14, pady=4, bd=0).pack(side='left', padx=(6, 0))

    def _do_create(self, dlg, title: str, start_dt: datetime, end_dt: datetime):
        try:
            create_event(title, start_dt, end_dt)
            if dlg is not None:
                self.root.after(0, dlg.destroy)
            self.root.after(2000, self._load_calendar)
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
