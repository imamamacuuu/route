import os

_DIR = os.path.dirname(__file__)
_HTML_PATH = os.path.join(_DIR, 'dashboard.html')

def get_dashboard_html() -> str:
    # ponytail: read from disk to allow hot-reloading; cache if disk IO becomes bottle
    if os.path.exists(_HTML_PATH):
        with open(_HTML_PATH, 'r', encoding='utf-8') as f:
            return f.read()
    return '<h1>Petani Gateway Console</h1>'

DASHBOARD_HTML = get_dashboard_html()
