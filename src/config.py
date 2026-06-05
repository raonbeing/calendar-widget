import os
import sys
import json


def _base_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


CONFIG_PATH = os.path.join(_base_dir(), 'secrets', 'config.json')

DEFAULTS = {
    'alpha': 0.85,
    'bg_widget': '#111118',
    'acc_event': '#4cc9f0',
    'acc_allday': '#f0c040',
}


def load_settings() -> dict:
    try:
        with open(CONFIG_PATH, encoding='utf-8') as f:
            data = json.load(f)
        return {k: data.get(k, v) for k, v in DEFAULTS.items()}
    except Exception:
        return dict(DEFAULTS)


def save_settings(settings: dict):
    try:
        to_save = {k: settings.get(k, v) for k, v in DEFAULTS.items()}
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(to_save, f, indent=2)
    except Exception:
        pass
