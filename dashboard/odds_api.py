import json
from dataclasses import dataclass
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request
from urllib.request import urlopen


BRAZIL_REGULATED_BOOKMAKER_KEYS = {
    'betfair_ex_eu',
    'betfair_ex_uk',
    'betfair',
    'betsson',
    'betclic',
    'superbet',
    'kto',
    'betano',
    'bet365',
    'novibet',
    'sportingbet',
    'stake',
    'estrelabet',
    'reals',
    'betnacional',
}

BRAZIL_REGULATED_BOOKMAKER_NAMES = {
    'betfair',
    'betsson',
    'betclic',
    'superbet',
    'kto',
    'betano',
    'bet365',
    'novibet',
    'sportingbet',
    'stake',
    'estrela bet',
    'estrelabet',
    'reals',
    'betnacional',
}


class OddsApiError(Exception):
    pass


@dataclass
class OddsApiClient:
    api_key: str
    base_url: str = 'https://api.the-odds-api.com/v4'
    timeout: int = 20

    def _get(self, path, params=None):
        request_params = {'apiKey': self.api_key}
        request_params.update(params or {})
        query = urlencode(request_params)
        url = f'{self.base_url}{path}'
        if query:
            url = f'{url}?{query}'
        request = Request(url)

        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = response.read().decode('utf-8')
                return json.loads(payload)
        except HTTPError as error:
            body = error.read().decode('utf-8', errors='replace')
            raise OddsApiError(f'Erro {error.code} da API: {body}') from error
        except OSError as error:
            raise OddsApiError(f'Falha ao conectar na API: {error}') from error

    def sports(self):
        return self._get('/sports/')

    def events(self, sport_key):
        return self._get(f'/sports/{sport_key}/events')

    def odds(self, sport_key, regions='eu', markets='h2h', bookmakers=''):
        params = {
            'regions': regions,
            'markets': markets,
        }
        if bookmakers:
            params['bookmakers'] = bookmakers
        return self._get(f'/sports/{sport_key}/odds/', params)


def summarize_odds(events, limit=5):
    summaries = []
    for event in events[:limit]:
        bookmakers = []
        for bookmaker in event.get('bookmakers', []):
            markets = []
            for market in bookmaker.get('markets', []):
                outcomes = [
                    f'{outcome.get("name")}: {outcome.get("price")}'
                    for outcome in market.get('outcomes', [])
                ]
                markets.append(
                    {
                        'key': market.get('key'),
                        'outcomes': outcomes,
                    }
                )
            bookmakers.append(
                {
                    'title': bookmaker.get('title'),
                    'markets': markets,
                }
            )

        summaries.append(
            {
                'event': f'{event.get("home_team")} x {event.get("away_team")}',
                'sport': event.get('sport_title'),
                'commence_time': event.get('commence_time'),
                'bookmakers': bookmakers,
            }
        )
    return summaries


def is_brazil_regulated_bookmaker(bookmaker):
    key = (bookmaker.get('key') or '').lower()
    title = (bookmaker.get('title') or '').lower()
    return key in BRAZIL_REGULATED_BOOKMAKER_KEYS or any(
        allowed_name in title for allowed_name in BRAZIL_REGULATED_BOOKMAKER_NAMES
    )


def detect_surebets(events, limit=10, brazil_regulated_only=False):
    opportunities = []

    for event in events:
        best_outcomes = {}

        for bookmaker in event.get('bookmakers', []):
            if brazil_regulated_only and not is_brazil_regulated_bookmaker(bookmaker):
                continue
            bookmaker_title = bookmaker.get('title')
            bookmaker_key = bookmaker.get('key')
            for market in bookmaker.get('markets', []):
                if market.get('key') != 'h2h':
                    continue
                for outcome in market.get('outcomes', []):
                    name = outcome.get('name')
                    price = outcome.get('price')
                    if not name or not price:
                        continue
                    current = best_outcomes.get(name)
                    if current is None or price > current['price']:
                        best_outcomes[name] = {
                            'name': name,
                            'price': float(price),
                            'bookmaker': bookmaker_title,
                            'bookmaker_key': bookmaker_key,
                        }

        if len(best_outcomes) < 2:
            continue

        outcomes = list(best_outcomes.values())
        implied_probability = sum(1 / outcome['price'] for outcome in outcomes)
        if implied_probability >= 1:
            continue

        profit_margin = (1 / implied_probability - 1) * 100
        opportunities.append(
            {
                'event': f'{event.get("home_team")} x {event.get("away_team")}',
                'sport': event.get('sport_title'),
                'commence_time': event.get('commence_time'),
                'implied_probability': implied_probability * 100,
                'profit_margin': profit_margin,
                'outcomes': sorted(outcomes, key=lambda item: item['name']),
            }
        )

    return sorted(opportunities, key=lambda item: item['profit_margin'], reverse=True)[:limit]


def build_odds_comparison(events, limit=10, brazil_regulated_only=False):
    comparisons = []

    for event in events[:limit]:
        bookmaker_names = []
        outcome_rows = {}

        for bookmaker in event.get('bookmakers', []):
            if brazil_regulated_only and not is_brazil_regulated_bookmaker(bookmaker):
                continue
            bookmaker_title = bookmaker.get('title')
            if bookmaker_title not in bookmaker_names:
                bookmaker_names.append(bookmaker_title)

            for market in bookmaker.get('markets', []):
                if market.get('key') != 'h2h':
                    continue
                for outcome in market.get('outcomes', []):
                    name = outcome.get('name')
                    price = outcome.get('price')
                    if not name or not price:
                        continue
                    row = outcome_rows.setdefault(
                        name,
                        {
                            'name': name,
                            'prices': {},
                            'best_price': 0,
                            'best_bookmaker': '',
                        },
                    )
                    row['prices'][bookmaker_title] = float(price)
                    if float(price) > row['best_price']:
                        row['best_price'] = float(price)
                        row['best_bookmaker'] = bookmaker_title

        if not outcome_rows:
            continue

        comparisons.append(
            {
                'event': f'{event.get("home_team")} x {event.get("away_team")}',
                'sport': event.get('sport_title'),
                'commence_time': event.get('commence_time'),
                'bookmakers': bookmaker_names,
                'outcomes': sorted(outcome_rows.values(), key=lambda item: item['name']),
            }
        )

    return comparisons
