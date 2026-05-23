import re
import urllib.error
import urllib.request
from html.parser import HTMLParser
from decimal import Decimal

from django.utils import timezone

from .models import Promotion
from .models import PromotionPage


KEYWORDS = [
    'freebet',
    'free bet',
    'aposta grátis',
    'aposta gratis',
    'cashback',
    'reembolso',
    'perdeu, ganhou',
    'perdeu ganhou',
    'odd turbinada',
    'odds turbinadas',
    'super odds',
    'bônus',
    'bonus',
]


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'noscript', 'svg'}:
            self.skip_depth += 1

    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'noscript', 'svg'} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data):
        if not self.skip_depth:
            text = data.strip()
            if text:
                self.parts.append(text)

    def text(self):
        return re.sub(r'\s+', ' ', ' '.join(self.parts)).strip()


def fetch_public_text(url, timeout=8):
    request = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'BetPilotPromotionScanner/1.0 (+public promotion discovery)',
            'Accept': 'text/html,application/xhtml+xml',
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or 'utf-8'
        html = response.read().decode(charset, errors='ignore')
    parser = TextExtractor()
    parser.feed(html)
    return parser.text()


def find_keyword_snippets(text):
    lower_text = text.lower()
    snippets = []
    for keyword in KEYWORDS:
        start = lower_text.find(keyword)
        if start == -1:
            continue
        left = max(start - 130, 0)
        right = min(start + 320, len(text))
        snippet = text[left:right].strip()
        if snippet and snippet not in snippets:
            snippets.append(snippet)
    return snippets


def detect_kind(snippet):
    lower = snippet.lower()
    if 'cashback' in lower or 'reembolso' in lower:
        return Promotion.Kind.CASHBACK
    if 'turbinad' in lower or 'super odds' in lower or 'boost' in lower:
        return Promotion.Kind.ODDS_BOOST
    if 'freebet' in lower or 'aposta grátis' in lower or 'aposta gratis' in lower:
        return Promotion.Kind.FREEBET
    return Promotion.Kind.BONUS


def detect_trigger(snippet):
    lower = snippet.lower()
    if 'ambos' in lower or 'qualquer resultado' in lower:
        return Promotion.Trigger.ANY
    if 'perder' in lower or 'perdeu' in lower or 'reembolso' in lower:
        return Promotion.Trigger.LOST
    if 'ganhar' in lower or 'venceu' in lower:
        return Promotion.Trigger.WON
    return Promotion.Trigger.LOST


def detect_money(snippet):
    matches = re.findall(r'R\$\s*([0-9]+(?:[.,][0-9]{1,2})?)', snippet, flags=re.IGNORECASE)
    if not matches:
        return Decimal('0.00')
    values = [Decimal(match.replace('.', '').replace(',', '.')) for match in matches]
    return max(values).quantize(Decimal('0.01'))


def detect_min_odd(snippet):
    match = re.search(r'odd(?:s)?(?: mínima| minima)?\D+([1-9][.,][0-9]{1,2})', snippet, flags=re.IGNORECASE)
    if not match:
        return Decimal('1.01')
    return Decimal(match.group(1).replace(',', '.')).quantize(Decimal('0.01'))


def build_title(snippet, bookmaker):
    words = snippet.split()
    title = ' '.join(words[:10]).strip(' -|.,')
    return title[:150] or f'Promoção {bookmaker.brand}'


def scan_promotion_page(page, timeout=8):
    try:
        text = fetch_public_text(page.url, timeout=timeout)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        page.last_scan_at = timezone.now()
        page.last_scan_note = f'Erro ao varrer: {exc}'[:180]
        page.save(update_fields=['last_scan_at', 'last_scan_note'])
        return {'created': 0, 'updated': 0, 'error': str(exc), 'matches': 0}

    snippets = find_keyword_snippets(text)
    created = 0
    updated = 0

    for snippet in snippets[:8]:
        title = build_title(snippet, page.bookmaker)
        _, was_created = Promotion.objects.update_or_create(
            bookmaker=page.bookmaker,
            source_url=page.url,
            title=title,
            defaults={
                'page': page,
                'kind': detect_kind(snippet),
                'trigger': detect_trigger(snippet),
                'freebet_amount': detect_money(snippet),
                'min_odd': detect_min_odd(snippet),
                'sport': 'Futebol',
                'public_text': snippet,
                'is_active': True,
                'detected_at': timezone.now(),
            },
        )
        created += 1 if was_created else 0
        updated += 0 if was_created else 1

    page.last_scan_at = timezone.now()
    page.last_scan_note = f'{len(snippets)} trecho(s) promocional(is) encontrado(s).'
    page.save(update_fields=['last_scan_at', 'last_scan_note'])
    return {'created': created, 'updated': updated, 'error': '', 'matches': len(snippets)}


def scan_user_promotion_pages(user, limit=None, timeout=8):
    pages = PromotionPage.objects.filter(bookmaker__owner=user, is_active=True).select_related('bookmaker')
    if limit:
        pages = pages[:limit]
    totals = {'created': 0, 'updated': 0, 'errors': [], 'pages': 0, 'matches': 0}
    for page in pages:
        result = scan_promotion_page(page, timeout=timeout)
        totals['pages'] += 1
        totals['created'] += result['created']
        totals['updated'] += result['updated']
        totals['matches'] += result['matches']
        if result['error']:
            totals['errors'].append(f'{page.bookmaker.brand}: {result["error"]}')
    return totals
