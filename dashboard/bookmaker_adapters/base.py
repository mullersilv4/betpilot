from dataclasses import dataclass
from decimal import Decimal
from html.parser import HTMLParser
import json
import os
import re
import unicodedata
from urllib.error import HTTPError
from urllib.parse import quote_plus
from urllib.parse import urljoin
from urllib.request import Request
from urllib.request import urlopen


class BookmakerAdapterError(Exception):
    pass


@dataclass
class EventMatch:
    bookmaker: str
    event_url: str
    home_team: str
    away_team: str
    matched_confidence: Decimal


@dataclass
class OddsQuote:
    bookmaker: str
    market: str
    selection: str
    odd: Decimal
    source_url: str


class BaseBookmakerAdapter:
    bookmaker = ''
    display_name = ''
    default_markets = ('Resultado Final',)
    request_delay_seconds = 2

    def find_event(self, home_team, away_team, start_time=None):
        raise NotImplementedError

    def get_event_odds(self, event_url, markets=None):
        raise NotImplementedError


class PlaceholderBookmakerAdapter(BaseBookmakerAdapter):
    def find_event(self, home_team, away_team, start_time=None):
        return None

    def get_event_odds(self, event_url, markets=None):
        return []


class LinkExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._current_href = None
        self._current_text = []

    def handle_starttag(self, tag, attrs):
        if tag != 'a':
            return
        attrs = dict(attrs)
        href = attrs.get('href')
        if href:
            self._current_href = href
            self._current_text = []

    def handle_data(self, data):
        if self._current_href:
            self._current_text.append(data)

    def handle_endtag(self, tag):
        if tag == 'a' and self._current_href:
            self.links.append(
                {
                    'href': self._current_href,
                    'text': ' '.join(part.strip() for part in self._current_text if part.strip()),
                }
            )
            self._current_href = None
            self._current_text = []


def normalize_text(value):
    value = unicodedata.normalize('NFKD', value or '')
    value = ''.join(char for char in value if not unicodedata.combining(char))
    value = re.sub(r'[^a-z0-9]+', ' ', value.lower())
    return re.sub(r'\s+', ' ', value).strip()


def decimal_from_value(value):
    if value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        decimal = Decimal(str(value))
    else:
        text = str(value).strip().replace(',', '.')
        match = re.search(r'\d+(?:\.\d+)?', text)
        if not match:
            return None
        decimal = Decimal(match.group(0))
    if decimal <= Decimal('1.00') or decimal > Decimal('1000'):
        return None
    return decimal.quantize(Decimal('0.001'))


class PublicWebBookmakerAdapter(BaseBookmakerAdapter):
    base_url = ''
    search_paths = ()
    event_path_terms = ('evento', 'event', 'futebol', 'football', 'soccer', 'apostas')
    timeout = 20
    use_playwright = True

    def should_use_playwright(self):
        return self.use_playwright and os.environ.get('BETPILOT_CRAWLER_PLAYWRIGHT', '1') != '0'

    def fetch_public_page(self, url):
        request = Request(
            url,
            headers={
                'Accept': 'text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8',
                'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.7',
                'User-Agent': 'BETPilot odds research/1.0',
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                html = response.read().decode('utf-8', errors='replace')
                if self.should_retry_with_playwright(html):
                    return self.fetch_rendered_page(url)
                return html
        except HTTPError as error:
            body = error.read().decode('utf-8', errors='replace')
            if self.should_use_playwright():
                return self.fetch_rendered_page(url)
            raise BookmakerAdapterError(f'HTTP {error.code} em {url}: {body[:160]}') from error
        except OSError as error:
            if self.should_use_playwright():
                return self.fetch_rendered_page(url)
            raise BookmakerAdapterError(f'Falha ao acessar {url}: {error}') from error

    def should_retry_with_playwright(self, html):
        normalized = normalize_text(html[:3000])
        if 'just a moment' in normalized or 'cloudflare' in normalized:
            return True
        return len(html) < 2000 or (
            '<script' in html.lower()
            and not any(term in normalized for term in ('bahia', 'botafogo', 'resultado final'))
        )

    def fetch_rendered_page(self, url):
        try:
            from playwright.sync_api import Error as PlaywrightError
            from playwright.sync_api import sync_playwright
        except ImportError as error:
            raise BookmakerAdapterError('Playwright não está instalado no ambiente.') from error

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--disable-software-rasterizer',
                        '--disable-blink-features=AutomationControlled',
                    ],
                )
                context = browser.new_context(
                    locale='pt-BR',
                    timezone_id='America/Sao_Paulo',
                    user_agent=(
                        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                        '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
                    ),
                    viewport={'width': 1366, 'height': 768},
                )
                page = context.new_page()
                page.goto(url, wait_until='domcontentloaded', timeout=self.timeout * 1000)
                try:
                    page.wait_for_load_state('networkidle', timeout=8000)
                except PlaywrightError:
                    pass
                page.wait_for_timeout(2500)
                html = page.content()
                context.close()
                browser.close()
                return html
        except PlaywrightError as error:
            raise BookmakerAdapterError(f'Playwright falhou ao acessar {url}: {error}') from error

    def search_urls(self, home_team, away_team):
        query = quote_plus(f'{home_team} {away_team}')
        yield self.base_url
        for path in self.search_paths:
            yield urljoin(self.base_url, path.format(query=query))

    def extract_links(self, html, source_url):
        parser = LinkExtractor()
        parser.feed(html)
        links = []
        for link in parser.links:
            href = link['href']
            if href.startswith('#') or href.startswith('javascript:'):
                continue
            links.append(
                {
                    'url': urljoin(source_url, href),
                    'text': link['text'],
                }
            )
        return links

    def score_event_candidate(self, link, home_team, away_team):
        haystack = normalize_text(f'{link["text"]} {link["url"]}')
        home = normalize_text(home_team)
        away = normalize_text(away_team)
        score = Decimal('0.00')
        if home and home in haystack:
            score += Decimal('45.00')
        if away and away in haystack:
            score += Decimal('45.00')
        if any(term in haystack for term in self.event_path_terms):
            score += Decimal('10.00')
        return min(score, Decimal('100.00'))

    def find_event(self, home_team, away_team, start_time=None):
        best = None
        best_score = Decimal('0.00')
        errors = []
        for url in self.search_urls(home_team, away_team):
            try:
                html = self.fetch_public_page(url)
            except BookmakerAdapterError as error:
                errors.append(str(error))
                continue
            for link in self.extract_links(html, url):
                score = self.score_event_candidate(link, home_team, away_team)
                if score > best_score:
                    best = link
                    best_score = score
            if best_score >= Decimal('90.00'):
                break
        if not best or best_score < Decimal('70.00'):
            if errors and len(errors) == len(list(self.search_urls(home_team, away_team))):
                raise BookmakerAdapterError(' | '.join(errors)[:220])
            return None
        return EventMatch(
            bookmaker=self.bookmaker,
            event_url=best['url'],
            home_team=home_team,
            away_team=away_team,
            matched_confidence=best_score,
        )

    def extract_json_candidates(self, html):
        candidates = []
        script_matches = re.findall(r'<script[^>]*>(.*?)</script>', html, flags=re.DOTALL | re.IGNORECASE)
        for script in script_matches:
            text = script.strip()
            if not text:
                continue
            if text.startswith('{') or text.startswith('['):
                candidates.append(text)
                continue
            for match in re.finditer(r'({(?:"props"|"events"|"markets"|"data"|"state")[\s\S]{100,}})', text):
                candidates.append(match.group(1))
        return candidates

    def iter_nested(self, value):
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from self.iter_nested(child)
        elif isinstance(value, list):
            for child in value:
                yield from self.iter_nested(child)

    def market_name(self, item):
        for key in ('marketName', 'market_name', 'name', 'title', 'label', 'typeName', 'displayName'):
            value = item.get(key)
            if isinstance(value, str):
                return value
        return ''

    def is_resultado_final_market(self, name):
        normalized = normalize_text(name)
        terms = (
            'resultado final',
            'resultado da partida',
            'vencedor da partida',
            'match result',
            'full time result',
            '1x2',
        )
        return any(term in normalized for term in terms)

    def extract_outcomes_from_market(self, market, source_url):
        outcomes = []
        for key in ('outcomes', 'selections', 'runners', 'prices', 'odds'):
            value = market.get(key)
            if isinstance(value, list):
                outcomes.extend(value)
            elif isinstance(value, dict):
                outcomes.extend(value.values())

        quotes = []
        for outcome in outcomes:
            if not isinstance(outcome, dict):
                continue
            selection = None
            for key in ('name', 'selectionName', 'runnerName', 'label', 'title', 'participantName', 'displayName'):
                if outcome.get(key):
                    selection = str(outcome[key])
                    break
            odd = None
            for key in ('odd', 'odds', 'price', 'decimal', 'decimalOdds', 'value'):
                odd = decimal_from_value(outcome.get(key))
                if odd:
                    break
            if selection and odd:
                quotes.append(
                    OddsQuote(
                        bookmaker=self.bookmaker,
                        market='Resultado Final',
                        selection=selection,
                        odd=odd,
                        source_url=source_url,
                    )
                )
        return quotes

    def extract_odds_from_json(self, html, source_url, markets):
        quotes = []
        for candidate in self.extract_json_candidates(html):
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            for item in self.iter_nested(payload):
                name = self.market_name(item)
                if name and self.is_resultado_final_market(name):
                    quotes.extend(self.extract_outcomes_from_market(item, source_url))
        return quotes

    def extract_odds_from_html(self, html, source_url):
        text = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html))
        quotes = []
        pattern = r'([A-Za-zÀ-ÿ0-9 ._-]{2,50})\s+(\d+[,.]\d{2,3})(?!\s*(?:em|rem|px|vh|vw|%))'
        for selection, odd in re.findall(pattern, text):
            normalized = normalize_text(selection)
            if normalized.endswith((' em', ' px', ' rem')) or 'font' in normalized:
                continue
            if normalized in {'empate', 'casa', 'fora'} or (
                len(normalized.split()) <= 4 and not re.search(r'\b(?:em|px|rem|auto|solid|none)\b', normalized)
            ):
                decimal = decimal_from_value(odd)
                if not decimal:
                    continue
                quotes.append(
                    OddsQuote(
                        bookmaker=self.bookmaker,
                        market='Resultado Final',
                        selection=selection.strip(),
                        odd=decimal,
                        source_url=source_url,
                    )
                )
        return quotes[:3] if len(quotes) >= 2 else []

    def get_event_odds(self, event_url, markets=None):
        markets = markets or self.default_markets
        html = self.fetch_public_page(event_url)
        quotes = self.extract_odds_from_json(html, event_url, markets)
        if quotes:
            return quotes[:3]
        return self.extract_odds_from_html(html, event_url)
