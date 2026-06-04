import os
import json

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
DEFAULT_ALPHA = 0.85


def load_alpha() -> float:
    try:
        with open(CONFIG_PATH, encoding='utf-8') as f:
            return float(json.load(f).get('alpha', DEFAULT_ALPHA))
    except Exception:
        return DEFAULT_ALPHA


def save_alpha(value: float):
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump({'alpha': round(value, 2)}, f)
    except Exception:
        pass
