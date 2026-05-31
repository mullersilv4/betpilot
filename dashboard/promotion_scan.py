import re
import urllib.error
import urllib.request
import unicodedata
from datetime import datetime
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

ACTION_KEYWORDS = [
    'aproveitar oferta',
    'ganhe',
    'receba',
    'participe',
    'ative',
    'cadastre',
    'faça uma aposta',
    'faca uma aposta',
]

EXPIRATION_KEYWORDS = [
    'expira',
    'válido até',
    'valido ate',
    'termos e condições',
    'termos e condicoes',
]

NOISE_KEYWORDS = [
    'entrar',
    'cadastro',
    'registre-se',
    'ajuda',
    'contato',
    'configurações',
    'configuracoes',
    'jogo responsável',
    'jogo responsavel',
    'verificação de identidade',
    'verificacao de identidade',
    'o cupom de apostas está vazio',
    'o cupom de apostas esta vazio',
    'ver mais',
    'como funciona',
    'como funcionam',
    'o que são',
    'o que sao',
    'descubra como',
]

AFFILIATE_KEYWORDS = [
    'afiliado',
    'afiliados',
    'afiliacao',
    'afiliação',
    'affiliate',
    'affiliates',
    'indique e ganhe',
    'convide e ganhe',
    'programa de indicação',
    'programa de indicacao',
    'refer a friend',
    'referral',
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
            'User-Agent': 'FreebetarPromotionScanner/1.0 (+public promotion discovery)',
            'Accept': 'text/html,application/xhtml+xml',
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or 'utf-8'
        html = response.read().decode(charset, errors='ignore')
    parser = TextExtractor()
    parser.feed(html)
    return parser.text()


def fetch_rendered_text(url, timeout=8):
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError('Playwright não instalado') from exc

    timeout_ms = timeout * 1000
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(
                    user_agent='FreebetarPromotionScanner/1.0 (+public promotion discovery)',
                    locale='pt-BR',
                )
                page.goto(url, wait_until='domcontentloaded', timeout=timeout_ms)
                try:
                    page.wait_for_load_state('networkidle', timeout=min(timeout_ms, 5000))
                except PlaywrightTimeoutError:
                    pass
                text = page.locator('body').inner_text(timeout=timeout_ms)
            finally:
                browser.close()
    except (PlaywrightError, PlaywrightTimeoutError) as exc:
        raise RuntimeError(str(exc)) from exc

    return re.sub(r'\s+', ' ', text).strip()


def fetch_scan_text(url, timeout=8, rendered=False):
    if rendered:
        try:
            return fetch_rendered_text(url, timeout=timeout), 'renderizada'
        except RuntimeError as exc:
            text = fetch_public_text(url, timeout=timeout)
            return text, f'simples, fallback renderizado: {exc}'
    return fetch_public_text(url, timeout=timeout), 'simples'


def find_keyword_snippets(text):
    lower_text = text.lower()
    snippets = []
    for keyword in KEYWORDS:
        start = 0
        while True:
            start = lower_text.find(keyword, start)
            if start == -1:
                break
            left = max(start - 90, 0)
            right = min(start + 260, len(text))
            snippet = clean_snippet(text[left:right])
            if snippet and snippet not in snippets:
                snippets.append(snippet)
            start += len(keyword)
    return snippets


def trim_offer_snippet(snippet):
    snippet = clean_snippet(snippet)
    expira_match = re.search(r'\bexpira:\s*\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}', snippet, flags=re.IGNORECASE)
    if not expira_match:
        return snippet

    before = snippet[:expira_match.start()]
    after = snippet[expira_match.start():]
    for marker in [
        'Ofertas de Esportes',
        'Ofertas de Cassino',
        'Vantagens Ferramentas',
        'Registre-se agora',
        'VER TUDO',
        'Início Esportes',
        'Inicio Esportes',
    ]:
        index = before.lower().rfind(marker.lower())
        if index != -1:
            before = before[index + len(marker):]

    before_words = before.split()
    title_context = ' '.join(before_words[-14:])
    return clean_snippet(f'{title_context} {after[:220]}')


def find_offer_snippets(text):
    snippets = []
    for chunk in re.split(r'\bAproveitar Oferta\b', text or '', flags=re.IGNORECASE):
        snippet = trim_offer_snippet(chunk)
        if 'expira:' not in normalize_search_text(snippet):
            continue
        if not contains_any(snippet, KEYWORDS):
            continue
        if snippet and snippet not in snippets:
            snippets.append(snippet)
    return snippets


def find_promotion_snippets(text):
    offer_snippets = find_offer_snippets(text)
    if offer_snippets:
        return offer_snippets
    keyword_snippets = find_keyword_snippets(text)
    return keyword_snippets


def clean_snippet(text):
    return re.sub(r'\s+', ' ', text or '').strip(' -|.,')


def normalize_search_text(text):
    normalized = unicodedata.normalize('NFKD', text or '')
    return ''.join(char for char in normalized if not unicodedata.combining(char)).lower()


def is_affiliate_promotion(text, url=''):
    target = normalize_search_text(f'{text} {url}')
    return any(normalize_search_text(keyword) in target for keyword in AFFILIATE_KEYWORDS)


def contains_any(text, keywords):
    normalized = normalize_search_text(text)
    return any(normalize_search_text(keyword) in normalized for keyword in keywords)


def promotion_score(snippet):
    normalized = normalize_search_text(snippet)
    score = 0

    if detect_money(snippet) > Decimal('0.00'):
        score += 3
    if contains_any(snippet, EXPIRATION_KEYWORDS):
        score += 2
    if contains_any(snippet, ACTION_KEYWORDS):
        score += 2
    if any(term in normalized for term in ['freebet', 'free bet', 'aposta gratis', 'cashback', 'reembolso', 'perdeu ganhou']):
        score += 2
    if any(term in normalized for term in ['super odds', 'odd turbinada', 'odds turbinadas']):
        score += 1
    if contains_any(snippet, NOISE_KEYWORDS):
        score -= 2
    if 'expira:' not in normalized and detect_money(snippet) == Decimal('0.00') and contains_any(snippet, NOISE_KEYWORDS):
        score -= 2
    if len(snippet.split()) < 6:
        score -= 1

    return score


def is_actionable_promotion(snippet):
    return promotion_score(snippet) >= 3


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
    matches = re.findall(r'R\$\s*([0-9][0-9.,]*)', snippet, flags=re.IGNORECASE)
    if not matches:
        return Decimal('0.00')
    values = [parse_money_value(match) for match in matches]
    return max(values).quantize(Decimal('0.01'))


def parse_money_value(value):
    value = value.strip()
    if ',' in value:
        return Decimal(value.replace('.', '').replace(',', '.'))
    if value.count('.') == 1 and len(value.rsplit('.', 1)[1]) <= 2:
        return Decimal(value)
    return Decimal(value.replace('.', ''))


def detect_min_odd(snippet):
    match = re.search(r'odd(?:s)?(?: mínima| minima)?\D+([1-9][.,][0-9]{1,2})', snippet, flags=re.IGNORECASE)
    if not match:
        return Decimal('1.01')
    return Decimal(match.group(1).replace(',', '.')).quantize(Decimal('0.01'))


def detect_expires_at(snippet):
    match = re.search(r'\bexpira:\s*(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})', snippet, flags=re.IGNORECASE)
    if not match:
        return None
    naive = datetime.strptime(f'{match.group(1)} {match.group(2)}', '%d/%m/%Y %H:%M')
    return timezone.make_aware(naive, timezone.get_current_timezone())


def build_rule_summary(snippet):
    snippet = clean_snippet(snippet)
    expira_match = re.search(r'\bexpira:\s*\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}', snippet, flags=re.IGNORECASE)
    if expira_match:
        summary = snippet[expira_match.end():]
    else:
        summary = snippet

    summary = re.sub(r'\bAproveitar Oferta\b.*$', '', summary, flags=re.IGNORECASE)
    summary = re.sub(r'^(👉|18\+\s*\|\s*)', '', summary).strip()
    words = summary.split()
    return ' '.join(words[:28]).strip(' -|.,')[:220]


def build_title(snippet, bookmaker):
    snippet = clean_snippet(snippet)
    expira_match = re.search(r'\bexpira:', snippet, flags=re.IGNORECASE)
    if expira_match:
        title = snippet[:expira_match.start()]
        title = re.sub(r'^\d{1,2}/\d{1,2}/\d{4}\s+\d{2}:\d{2}\s+', '', title).strip(' -|.,')
        title = re.sub(r'^(Ver mais|Aproveitar Oferta|Promoções|Ofertas|VER TUDO(?: \(\d+\))?)\s+', '', title, flags=re.IGNORECASE)
        title = clean_title(title)
        if title:
            return title[:150]

    candidates = []
    for pattern in [
        r'([^.!?]{8,120}?)(?:\s+Expira:|\s+expira:)',
        r'(?:Aproveitar Oferta\s+)([^.!?]{8,120}?)(?:\s+Expira:|\s+expira:|$)',
        r'([^.!?]{8,120}?(?:freebet|aposta grátis|aposta gratis|cashback|super odds|odds turbinadas|odd turbinada)[^.!?]{0,80})',
    ]:
        candidates.extend(match.strip(' -|.,') for match in re.findall(pattern, snippet, flags=re.IGNORECASE))

    title = ''
    if candidates:
        title = max(candidates, key=promotion_score)
    else:
        words = snippet.split()
        title = ' '.join(words[:10]).strip(' -|.,')

    title = re.sub(r'^(Ver mais|Aproveitar Oferta|Promoções|Ofertas)\s+', '', title, flags=re.IGNORECASE)
    title = clean_title(title)
    return title[:150] or f'Promoção {bookmaker.brand}'


def clean_title(title):
    title = clean_snippet(title)
    for signal in [
        'Aposta Grátis',
        'Aposta Gratis',
        'Ganhe',
        'Comece',
        'Cashback',
        'Aposta Protegida',
        'SuperOdds',
        'Super Odds',
        'Odd Turbinada',
    ]:
        match = list(re.finditer(re.escape(signal), title, flags=re.IGNORECASE))
        if match:
            title = title[match[-1].start():]
            break
    title = re.sub(r'\bAproveitar Oferta\b.*$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\bExpira:.*$', '', title, flags=re.IGNORECASE)
    return clean_snippet(title)


def scan_promotion_page(page, timeout=8, rendered=False):
    try:
        text, scan_mode = fetch_scan_text(page.url, timeout=timeout, rendered=rendered)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError, RuntimeError) as exc:
        page.last_scan_at = timezone.now()
        page.last_scan_note = f'Erro ao varrer: {exc}'[:180]
        page.save(update_fields=['last_scan_at', 'last_scan_note'])
        return {'created': 0, 'updated': 0, 'expired': 0, 'error': str(exc), 'matches': 0, 'skipped': 0}

    snippets = find_promotion_snippets(text)
    created = 0
    updated = 0
    active_ids = []
    skipped = 0
    seen_titles = set()

    for snippet in snippets[:8]:
        if is_affiliate_promotion(snippet, page.url):
            skipped += 1
            continue
        if not is_actionable_promotion(snippet):
            skipped += 1
            continue
        title = build_title(snippet, page.bookmaker)
        title_key = normalize_search_text(title)
        if title_key in seen_titles:
            skipped += 1
            continue
        seen_titles.add(title_key)
        promotion, was_created = Promotion.objects.update_or_create(
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
                'rule_summary': build_rule_summary(snippet),
                'source_type': Promotion.SourceType.OFFICIAL,
                'source_name': page.bookmaker.brand,
                'validation_status': Promotion.ValidationStatus.CONFIRMED_OFFICIAL,
                'expires_at': detect_expires_at(snippet),
                'is_active': True,
                'detected_at': timezone.now(),
            },
        )
        active_ids.append(promotion.id)
        created += 1 if was_created else 0
        updated += 0 if was_created else 1

    expired = 0
    if snippets:
        stale_promotions = Promotion.objects.filter(page=page, is_active=True)
        if active_ids:
            stale_promotions = stale_promotions.exclude(id__in=active_ids)
        expired = stale_promotions.update(
            is_active=False,
            validation_status=Promotion.ValidationStatus.EXPIRED,
        )

    page.last_scan_at = timezone.now()
    page.last_scan_note = (
        f'{len(snippets)} trecho(s); {created} criada(s); {updated} atualizada(s); '
        f'{expired} expirada(s); {skipped} ignorada(s). Leitura {scan_mode}.'
    )[:180]
    page.save(update_fields=['last_scan_at', 'last_scan_note'])
    return {
        'created': created,
        'updated': updated,
        'expired': expired,
        'error': '',
        'matches': len(snippets),
        'skipped': skipped,
    }


def scan_user_promotion_pages(user, limit=None, timeout=8, rendered=False):
    pages = PromotionPage.objects.filter(bookmaker__owner=user, is_active=True).select_related('bookmaker')
    if limit:
        pages = pages[:limit]
    totals = {'created': 0, 'updated': 0, 'expired': 0, 'errors': [], 'pages': 0, 'matches': 0, 'skipped': 0}
    for page in pages:
        result = scan_promotion_page(page, timeout=timeout, rendered=rendered)
        totals['pages'] += 1
        totals['created'] += result['created']
        totals['updated'] += result['updated']
        totals['expired'] += result['expired']
        totals['matches'] += result['matches']
        totals['skipped'] += result['skipped']
        if result['error']:
            totals['errors'].append(f'{page.bookmaker.brand}: {result["error"]}')
    totals['expired'] += dedupe_active_promotions(user)
    return totals


def dedupe_active_promotions(user):
    promotions = Promotion.objects.filter(bookmaker__owner=user, is_active=True).select_related('bookmaker')
    seen = set()
    expired = 0
    for promotion in promotions:
        key = (promotion.bookmaker_id, normalize_search_text(promotion.title))
        if key in seen:
            promotion.is_active = False
            promotion.validation_status = Promotion.ValidationStatus.EXPIRED
            promotion.save(update_fields=['is_active', 'validation_status'])
            expired += 1
        else:
            seen.add(key)
    return expired
