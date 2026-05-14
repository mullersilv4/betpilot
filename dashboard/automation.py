import csv
import re
from decimal import Decimal
from decimal import InvalidOperation
from io import StringIO

from django.utils.dateparse import parse_datetime

from .forms import BetForm
from .models import Bankroll
from .models import Bet


FIELD_ALIASES = {
    'banca': 'bankroll',
    'bankroll': 'bankroll',
    'esporte': 'sport',
    'sport': 'sport',
    'competicao': 'competition',
    'competição': 'competition',
    'competition': 'competition',
    'jogo': 'game',
    'evento': 'game',
    'game': 'game',
    'mercado': 'market',
    'market': 'market',
    'estrategia': 'strategy',
    'estratégia': 'strategy',
    'tipster': 'strategy',
    'tipo': 'entry_type',
    'entry_type': 'entry_type',
    'data': 'event_date',
    'event_date': 'event_date',
    'odd': 'odds',
    'odds': 'odds',
    'valor': 'stake',
    'stake': 'stake',
    'comissao': 'exchange_commission',
    'comissão': 'exchange_commission',
    'status': 'status',
    'resultado': 'status',
    'placar': 'exact_score',
    'resultado_exato': 'exact_score',
    'link': 'game_link',
    'obs': 'notes',
    'observacao': 'notes',
    'observação': 'notes',
}


def normalize_decimal(value):
    return Decimal(str(value).strip().replace('R$', '').replace(',', '.'))


def normalize_status(value):
    if not value:
        return Bet.Status.OPEN
    if value in Bet.Status.values:
        return value
    status_map = {
        'aberta': Bet.Status.OPEN,
        'aberto': Bet.Status.OPEN,
        'open': Bet.Status.OPEN,
        'ganha': Bet.Status.WON,
        'green': Bet.Status.WON,
        'won': Bet.Status.WON,
        'perdida': Bet.Status.LOST,
        'red': Bet.Status.LOST,
        'lost': Bet.Status.LOST,
    }
    return status_map.get(value.lower(), value)


def normalize_entry_type(value):
    if not value:
        return Bet.EntryType.PRE_MATCH
    if value in Bet.EntryType.values:
        return value
    entry_map = {
        'pre-live': Bet.EntryType.PRE_MATCH,
        'pre': Bet.EntryType.PRE_MATCH,
        'pre_match': Bet.EntryType.PRE_MATCH,
        'prematch': Bet.EntryType.PRE_MATCH,
        'ao vivo': Bet.EntryType.LIVE,
        'live': Bet.EntryType.LIVE,
        'inplay': Bet.EntryType.LIVE,
    }
    return entry_map.get(value.lower(), value)


def parse_event_date(value):
    if not value:
        return None
    return parse_datetime(str(value).replace(' ', 'T'))


def data_from_parts(parts):
    legacy_format = len(parts) < 9
    if legacy_format:
        bankroll_name, game, market, odds, stake = parts[:5]
        return {
            'bankroll_name': bankroll_name,
            'sport': 'Futebol',
            'competition': '',
            'game': game,
            'market': market,
            'strategy': '',
            'entry_type': Bet.EntryType.PRE_MATCH,
            'event_date': None,
            'odds': odds,
            'stake': stake,
            'exchange_commission': parts[5] if len(parts) >= 6 and parts[5] else '0',
            'status': parts[6] if len(parts) >= 7 and parts[6] else Bet.Status.OPEN,
            'exact_score': '',
            'game_link': '',
            'notes': '',
        }

    (
        bankroll_name,
        sport,
        competition,
        game,
        market,
        strategy,
        entry_type,
        event_date,
        odds,
        stake,
        *rest,
    ) = parts
    return {
        'bankroll_name': bankroll_name,
        'sport': sport or 'Futebol',
        'competition': competition,
        'game': game,
        'market': market,
        'strategy': strategy,
        'entry_type': entry_type,
        'event_date': event_date,
        'odds': odds,
        'stake': stake,
        'exchange_commission': rest[0] if len(rest) >= 1 and rest[0] else '0',
        'status': rest[1] if len(rest) >= 2 and rest[1] else Bet.Status.OPEN,
        'exact_score': rest[2] if len(rest) >= 3 else '',
        'game_link': rest[3] if len(rest) >= 4 else '',
        'notes': rest[4] if len(rest) >= 5 else '',
    }


def data_from_label_text(line):
    matches = re.findall(r'([\wçãõáéíóúàê ]+)\s*[:=]\s*([^;|]+)', line, flags=re.I)
    if not matches:
        return None

    data = {}
    for raw_key, value in matches:
        key = FIELD_ALIASES.get(raw_key.strip().lower())
        if key:
            data[key] = value.strip()

    if 'bankroll' not in data or 'game' not in data or 'market' not in data:
        return None
    if 'odds' not in data or 'stake' not in data:
        return None

    return {
        'bankroll_name': data['bankroll'],
        'sport': data.get('sport', 'Futebol'),
        'competition': data.get('competition', ''),
        'game': data['game'],
        'market': data['market'],
        'strategy': data.get('strategy', ''),
        'entry_type': data.get('entry_type', Bet.EntryType.PRE_MATCH),
        'event_date': data.get('event_date'),
        'odds': data['odds'],
        'stake': data['stake'],
        'exchange_commission': data.get('exchange_commission', '0'),
        'status': data.get('status', Bet.Status.OPEN),
        'exact_score': data.get('exact_score', ''),
        'game_link': data.get('game_link', ''),
        'notes': data.get('notes', ''),
    }


def detect_duplicate(data, bankroll):
    return Bet.objects.filter(
        bankroll=bankroll,
        game__iexact=data['game'],
        market__iexact=data['market'],
        odds=data['odds'],
        stake=data['stake'],
        status=Bet.Status.OPEN,
    ).exists()


def odd_alert(data):
    odds = data['odds']
    if odds < Decimal('1.20'):
        return 'Odd muito baixa. Confira se a entrada foi digitada corretamente.'
    if odds > Decimal('5.00'):
        return 'Odd alta. Revise stake, mercado e risco antes de confirmar.'
    return None


def normalize_bet_data(raw_data, user):
    try:
        bankroll = Bankroll.objects.get(owner=user, name__iexact=raw_data['bankroll_name'])
    except Bankroll.DoesNotExist:
        raise ValueError(f'banca "{raw_data["bankroll_name"]}" nao encontrada.')

    try:
        odds = normalize_decimal(raw_data['odds'])
        stake = normalize_decimal(raw_data['stake'])
        commission = normalize_decimal(raw_data.get('exchange_commission') or '0')
    except (InvalidOperation, ValueError):
        raise ValueError('odd, valor ou comissao invalida.')

    return bankroll, {
        'bankroll': bankroll.id,
        'sport': raw_data.get('sport') or 'Futebol',
        'competition': raw_data.get('competition') or '',
        'game': raw_data['game'],
        'market': raw_data['market'],
        'strategy': raw_data.get('strategy') or '',
        'event_date': parse_event_date(raw_data.get('event_date')),
        'entry_type': normalize_entry_type(raw_data.get('entry_type')),
        'odds': odds,
        'stake': stake,
        'exchange_commission': commission,
        'status': normalize_status(raw_data.get('status')),
        'exact_score': raw_data.get('exact_score') or '',
        'game_link': raw_data.get('game_link') or '',
        'notes': raw_data.get('notes') or '',
    }


def import_bets_from_text(raw_text, user):
    imported = []
    errors = []
    warnings = []

    for line_number, raw_line in enumerate(raw_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        labeled_data = data_from_label_text(line) if re.search(r'[\wçãõáéíóúàê ]+\s*[:=]', line, re.I) else None
        if labeled_data is not None:
            raw_data = labeled_data
        elif ';' in line:
            parts = [part.strip() for part in line.split(';')]
            if len(parts) < 5:
                errors.append(f'Linha {line_number}: formato incompleto.')
                continue
            raw_data = data_from_parts(parts)
        else:
            raw_data = data_from_label_text(line)
            if raw_data is None:
                errors.append(f'Linha {line_number}: nao consegui identificar os campos.')
                continue

        try:
            bankroll, data = normalize_bet_data(raw_data, user)
        except ValueError as exc:
            errors.append(f'Linha {line_number}: {exc}')
            continue

        if detect_duplicate(data, bankroll):
            warnings.append(f'Linha {line_number}: aposta duplicada ignorada.')
            continue

        alert = odd_alert(data)
        if alert:
            warnings.append(f'Linha {line_number}: {alert}')

        form = BetForm(data=data, user=user)
        if form.is_valid():
            imported.append(form.save())
        else:
            errors.append(f'Linha {line_number}: {form.errors.as_text()}')

    return imported, errors, warnings


def import_bets_from_csv(uploaded_file, user):
    decoded = uploaded_file.read().decode('utf-8-sig')
    reader = csv.DictReader(StringIO(decoded))
    lines = []
    for row in reader:
        normalized = {FIELD_ALIASES.get(key.strip().lower(), key): value for key, value in row.items()}
        lines.append(
            ';'.join(
                [
                    normalized.get('bankroll', ''),
                    normalized.get('sport', 'Futebol'),
                    normalized.get('competition', ''),
                    normalized.get('game', ''),
                    normalized.get('market', ''),
                    normalized.get('strategy', ''),
                    normalized.get('entry_type', Bet.EntryType.PRE_MATCH),
                    normalized.get('event_date', ''),
                    normalized.get('odds', ''),
                    normalized.get('stake', ''),
                    normalized.get('exchange_commission', '0'),
                    normalized.get('status', Bet.Status.OPEN),
                    normalized.get('exact_score', ''),
                    normalized.get('game_link', ''),
                    normalized.get('notes', ''),
                ]
            )
        )
    return import_bets_from_text('\n'.join(lines), user)
