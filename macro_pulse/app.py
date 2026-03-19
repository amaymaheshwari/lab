import os
import json
import time
import requests
from abc import ABC, abstractmethod
from flask import Flask, render_template, jsonify

app = Flask(__name__)

CACHE_DIR = os.path.join(os.path.dirname(__file__), 'data', 'cache')
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_TTL = 3600  # 1 hour


# --- Cache Helpers ---
def cache_read(key):
    path = os.path.join(CACHE_DIR, f'{key}.json')
    if os.path.exists(path):
        with open(path) as f:
            cached = json.load(f)
        if time.time() - cached.get('timestamp', 0) < CACHE_TTL:
            return cached.get('data')
    return None


def cache_write(key, data):
    path = os.path.join(CACHE_DIR, f'{key}.json')
    with open(path, 'w') as f:
        json.dump({'timestamp': time.time(), 'data': data}, f)


# --- Data Providers ---
class MacroProvider(ABC):
    @abstractmethod
    def get_series(self, series_id, limit=24):
        pass


class FredProvider(MacroProvider):
    """Fetches data from the Federal Reserve Economic Data (FRED) API."""
    BASE = 'https://api.stlouisfed.org/fred/series/observations'

    def __init__(self):
        self.api_key = os.environ.get('FRED_API_KEY')

    def get_series(self, series_id, limit=24):
        if not self.api_key:
            return None
        cached = cache_read(series_id)
        if cached:
            return cached
        try:
            r = requests.get(self.BASE, params={
                'series_id': series_id,
                'api_key': self.api_key,
                'file_type': 'json',
                'limit': limit,
                'sort_order': 'desc'
            }, timeout=10)
            r.raise_for_status()
            obs = r.json().get('observations', [])
            data = [
                {'date': o['date'], 'value': float(o['value'])}
                for o in reversed(obs)
                if o['value'] != '.'
            ]
            cache_write(series_id, data)
            return data
        except Exception:
            return None


class WorldBankProvider:
    """Fetches GDP data from the World Bank Open Data API (no key required)."""
    BASE = 'https://api.worldbank.org/v2/country/{iso}/indicator/{indicator}'

    def get_gdp_growth(self, iso, mrv=6):
        key = f'wb_{iso}_gdp'
        cached = cache_read(key)
        if cached:
            return cached
        try:
            url = self.BASE.format(iso=iso, indicator='NY.GDP.MKTP.KD.ZG')
            r = requests.get(url, params={'format': 'json', 'mrv': mrv}, timeout=10)
            r.raise_for_status()
            body = r.json()
            if len(body) < 2 or not body[1]:
                return None
            entries = [
                {'year': e['date'], 'value': round(e['value'], 2)}
                for e in body[1] if e['value'] is not None
            ]
            entries.sort(key=lambda x: x['year'])
            cache_write(key, entries)
            return entries
        except Exception:
            return None


fred = FredProvider()
worldbank = WorldBankProvider()

G7 = [
    ('USA', 'United States'),
    ('GBR', 'United Kingdom'),
    ('DEU', 'Germany'),
    ('FRA', 'France'),
    ('ITA', 'Italy'),
    ('CAN', 'Canada'),
    ('JPN', 'Japan'),
]


# --- Routes ---
@app.route('/')
def index():
    has_fred_key = bool(os.environ.get('FRED_API_KEY'))
    has_gemini_key = bool(os.environ.get('GEMINI_API_KEY'))
    return render_template('index.html', has_fred_key=has_fred_key, has_gemini_key=has_gemini_key)


@app.route('/api/macro')
def api_macro():
    series = {
        'cpi':          fred.get_series('CPIAUCSL', 24),
        'unemployment': fred.get_series('UNRATE', 24),
        'treasury_10y': fred.get_series('DGS10', 60),
        'fed_funds':    fred.get_series('FEDFUNDS', 24),
        'sp500':        fred.get_series('SP500', 90),
    }

    cpi_yoy = None
    if series['cpi'] and len(series['cpi']) >= 13:
        latest = series['cpi'][-1]['value']
        year_ago = series['cpi'][-13]['value']
        cpi_yoy = round(((latest - year_ago) / year_ago) * 100, 2)

    return jsonify({**series, 'cpi_yoy': cpi_yoy})


@app.route('/api/gdp')
def api_gdp():
    result = []
    for iso, name in G7:
        data = worldbank.get_gdp_growth(iso)
        if data:
            result.append({'iso': iso, 'name': name, 'data': data})
    return jsonify(result)


@app.route('/api/context')
def api_context():
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        return jsonify({'error': 'GEMINI_API_KEY not configured.'}), 400

    snapshot = {}
    for key, series_id, limit in [
        ('cpi',          'CPIAUCSL', 24),
        ('unemployment', 'UNRATE',   24),
        ('treasury_10y', 'DGS10',    60),
        ('fed_funds',    'FEDFUNDS', 24),
    ]:
        data = fred.get_series(series_id, limit)
        if data:
            snapshot[key] = data[-1]['value']

    cpi_yoy = None
    cpi_data = fred.get_series('CPIAUCSL', 24)
    if cpi_data and len(cpi_data) >= 13:
        cpi_yoy = round(((cpi_data[-1]['value'] - cpi_data[-13]['value']) / cpi_data[-13]['value']) * 100, 2)

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')

        prompt = f"""You are a macroeconomic historian. Based on the following current US economic indicators,
identify which historical financial era this most closely resembles from this list:

- Tulip Mania (1636-1637)
- South Sea Bubble (1720)
- Great Crash (1929)
- Japan's Lost Decade (1989-1992)
- Asian Financial Crisis (1997-1998)
- Dot-Com Bubble (1999-2002)
- Great Recession (2007-2009)
- COVID Everything Bubble (2020-2022)
- None of the above (stable / no clear historical parallel)

Current US Macro Indicators:
- CPI Year-over-Year Inflation: {cpi_yoy}%
- Unemployment Rate: {snapshot.get('unemployment', 'N/A')}%
- 10-Year Treasury Yield: {snapshot.get('treasury_10y', 'N/A')}%
- Federal Funds Rate: {snapshot.get('fed_funds', 'N/A')}%

Respond in exactly this JSON format (no markdown, raw JSON only):
{{
  "era": "<era name from the list>",
  "confidence": "<High/Medium/Low>",
  "reasoning": "<2-3 sentences explaining which indicators match and why>",
  "key_risk": "<the single biggest macro risk right now in one sentence>"
}}"""

        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith('```'):
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
        result = json.loads(text.strip())
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("Macro Pulse running on http://localhost:5004")
    app.run(debug=True, port=5004)
