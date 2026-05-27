import json
import re
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

BRAZIL_PRIORITY_BOOKMAKER_TERMS = {
    'bet365',
    'betano',
    'superbet',
    'novibet',
    'jogo_de_ouro',
    'jogodeouro',
    'bolsa_de_aposta',
    'bolsadeaposta',
    'betfair',
    'pagol',
    'pago',
    'sportingbet',
    'estrela_bet',
    'estrelabet',
    'esportes_da_sorte',
    'esportesdasorte',
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
        request = Request(
            url,
            headers={
                'Accept': 'application/json',
                'User-Agent': 'BETPilot/1.0 (+https://localhost)',
            },
        )

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

    def scores(self, sport_key, days_from=3, event_ids=None):
        params = {'daysFrom': days_from}
        if event_ids:
            params['eventIds'] = ','.join(event_ids)
        return self._get(f'/sports/{sport_key}/scores/', params)

    def odds(self, sport_key, regions='eu', markets='h2h', bookmakers=''):
        params = {
            'markets': markets,
        }
        if bookmakers:
            params['bookmakers'] = bookmakers
        else:
            params['regions'] = regions
        return self._get(f'/sports/{sport_key}/odds/', params)

    def event_odds(self, sport_key, event_id, regions='eu', markets='h2h', bookmakers=''):
        params = {
            'markets': markets,
        }
        if bookmakers:
            params['bookmakers'] = bookmakers
        else:
            params['regions'] = regions
        return self._get(f'/sports/{sport_key}/events/{event_id}/odds/', params)


@dataclass
class OddsPapiClient:
    api_key: str
    base_url: str = 'https://api.oddspapi.io/v4'
    timeout: int = 20

    def _get(self, path, params=None):
        request_params = {'apiKey': self.api_key}
        request_params.update(params or {})
        query = urlencode(request_params)
        url = f'{self.base_url}{path}'
        if query:
            url = f'{url}?{query}'
        request = Request(
            url,
            headers={
                'Accept': 'application/json',
                'User-Agent': 'BETPilot/1.0 (+https://localhost)',
            },
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = response.read().decode('utf-8')
                return json.loads(payload)
        except HTTPError as error:
            body = error.read().decode('utf-8', errors='replace')
            raise OddsApiError(f'Erro {error.code} da OddsPapi: {body}') from error
        except OSError as error:
            raise OddsApiError(f'Falha ao conectar na OddsPapi: {error}') from error

    def sports(self, language='en'):
        return self._get('/sports', {'language': language})

    def bookmakers(self):
        return self._get('/bookmakers')

    def tournaments(self, sport_id, language='en'):
        return self._get('/tournaments', {'sportId': sport_id, 'language': language})

    def fixtures(
        self,
        sport_id=None,
        tournament_id=None,
        from_time='',
        to_time='',
        status_id=0,
        has_odds=True,
        bookmakers='',
        language='en',
    ):
        params = {'language': language}
        if sport_id is not None:
            params['sportId'] = sport_id
        if tournament_id is not None:
            params['tournamentId'] = tournament_id
        if from_time:
            params['from'] = from_time
        if to_time:
            params['to'] = to_time
        if status_id is not None:
            params['statusId'] = status_id
        if has_odds is not None:
            params['hasOdds'] = str(bool(has_odds)).lower()
        if bookmakers:
            params['bookmakers'] = bookmakers
        return self._get('/fixtures', params)

    def odds(self, fixture_id, bookmakers='', language='en', verbosity=3, odds_format='decimal'):
        params = {
            'fixtureId': fixture_id,
            'language': language,
            'verbosity': verbosity,
            'oddsFormat': odds_format,
        }
        if bookmakers:
            params['bookmakers'] = bookmakers
        return self._get('/odds', params)

    def odds_by_tournaments(
        self,
        tournament_ids,
        bookmakers='',
        language='en',
        verbosity=3,
        odds_format='decimal',
    ):
        params = {
            'tournamentIds': tournament_ids,
            'language': language,
            'verbosity': verbosity,
            'oddsFormat': odds_format,
        }
        if bookmakers:
            params['bookmakers'] = bookmakers
        return self._get('/odds-by-tournaments', params)


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


def normalize_bookmaker_text(value):
    return re.sub(r'[^a-z0-9]+', '_', (value or '').lower()).strip('_')


def matches_allowed_bookmaker(bookmaker, allowed_terms):
    if not allowed_terms:
        return True
    key = normalize_bookmaker_text(bookmaker.get('key'))
    title = normalize_bookmaker_text(bookmaker.get('title'))
    return any(
        term and (term == key or term == title or term in title)
        for term in allowed_terms
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


def build_event_odds_board(event, brazil_regulated_only=False, allowed_bookmaker_terms=None):
    allowed_bookmaker_terms = [
        normalize_bookmaker_text(term)
        for term in (allowed_bookmaker_terms or [])
        if normalize_bookmaker_text(term)
    ]

    def collect_bookmakers(use_allowed_filter):
        outcome_names = []
        bookmakers = []
        for bookmaker in event.get('bookmakers', []):
            if brazil_regulated_only and not is_brazil_regulated_bookmaker(bookmaker):
                continue
            if (
                use_allowed_filter
                and allowed_bookmaker_terms
                and not matches_allowed_bookmaker(bookmaker, allowed_bookmaker_terms)
            ):
                continue

            outcomes = {}
            for market in bookmaker.get('markets', []):
                if market.get('key') != 'h2h':
                    continue
                for outcome in market.get('outcomes', []):
                    name = outcome.get('name')
                    price = outcome.get('price')
                    if not name or price is None:
                        continue
                    if name not in outcome_names:
                        outcome_names.append(name)
                    outcomes[name] = float(price)

            if outcomes:
                bookmakers.append(
                    {
                        'key': bookmaker.get('key') or '',
                        'title': bookmaker.get('title') or '',
                        'last_update': bookmaker.get('last_update') or '',
                        'outcomes': outcomes,
                    }
                )
        return outcome_names, bookmakers

    outcome_names, bookmakers = collect_bookmakers(use_allowed_filter=True)
    filter_note = ''
    if allowed_bookmaker_terms and len(bookmakers) < 2:
        fallback_outcome_names, fallback_bookmakers = collect_bookmakers(use_allowed_filter=False)
        if len(fallback_bookmakers) > len(bookmakers):
            outcome_names = fallback_outcome_names
            bookmakers = fallback_bookmakers
            filter_note = (
                'Poucas casas prioritárias disponíveis para este jogo; '
                'mostrando também outras casas retornadas pela API.'
            )

    return {
        'event': f'{event.get("home_team")} x {event.get("away_team")}'.strip(' x'),
        'sport': event.get('sport_title') or '',
        'commence_time': event.get('commence_time') or '',
        'outcome_names': outcome_names,
        'bookmakers': bookmakers,
        'filter_note': filter_note,
    }
