import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from decimal import InvalidOperation

from django.db import transaction

from .models import Bet
from .models import BankrollTransaction
from .models import FreeBet


@dataclass
class SettlementDecision:
    status: str
    reason: str


def normalize_text(value):
    normalized = unicodedata.normalize('NFKD', value or '')
    ascii_text = normalized.encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'\s+', ' ', ascii_text.lower()).strip()


def score_by_team(event):
    scores = {}
    for item in event.get('scores') or []:
        name = item.get('name')
        score = item.get('score')
        if not name or score is None:
            continue
        try:
            scores[normalize_text(name)] = Decimal(str(score))
        except InvalidOperation:
            continue
    return scores


def get_event_scores(bet, event):
    scores = score_by_team(event)
    home_name = normalize_text(bet.home_team or event.get('home_team') or '')
    away_name = normalize_text(bet.away_team or event.get('away_team') or '')
    if not home_name or not away_name:
        return None
    if home_name not in scores or away_name not in scores:
        return None
    return scores[home_name], scores[away_name]


def market_has_multiple_intents(market_text):
    text = normalize_text(market_text)
    separators = [' e ', ' + ', ' combinado ', ' dupla ']
    if ' over ' in f' {text} ' or ' under ' in f' {text} ':
        winner_terms = [' vence', ' ganha', ' empate', ' casa', ' fora', ' mandante', ' visitante']
        return any(term in f' {text} ' for term in winner_terms) or any(
            separator in f' {text} ' for separator in separators
        )
    return any(separator in f' {text} ' for separator in separators)


def parse_total_market(market_text):
    text = normalize_text(market_text).replace(',', '.')
    match = re.search(
        r'\b(over|under|mais de|menos de|acima de|abaixo de)\s*(\d+(?:\.\d+)?)',
        text,
    )
    if not match:
        return None
    side = match.group(1)
    threshold = Decimal(match.group(2))
    if side in {'over', 'mais de', 'acima de'}:
        return 'over', threshold
    return 'under', threshold


def resolve_total_market(bet, event):
    return resolve_total_market_text(bet.market, bet, event)


def resolve_total_market_text(market_text, bet, event):
    parsed = parse_total_market(market_text)
    if parsed is None:
        return None
    scores = get_event_scores(bet, event)
    if scores is None:
        return None
    side, threshold = parsed
    total_goals = scores[0] + scores[1]
    if total_goals == threshold:
        return None
    won = total_goals > threshold if side == 'over' else total_goals < threshold
    return SettlementDecision(
        status=Bet.Status.WON if won else Bet.Status.LOST,
        reason=f'Placar final {scores[0]}x{scores[1]}',
    )


def parse_winner_market(bet):
    return parse_winner_market_text(bet.market, bet)


def parse_winner_market_text(market_text, bet):
    text = f' {normalize_text(market_text)} '
    home = normalize_text(bet.home_team)
    away = normalize_text(bet.away_team)
    candidates = []

    if ' empate ' in text or text.strip() in {'x', 'draw', 'empate'}:
        candidates.append('draw')
    if home and home in text:
        candidates.append('home')
    if away and away in text:
        candidates.append('away')
    if any(term in text for term in [' casa ', ' mandante ', ' home ', ' 1 ']):
        candidates.append('home')
    if any(term in text for term in [' fora ', ' visitante ', ' away ', ' 2 ']):
        candidates.append('away')

    unique_candidates = set(candidates)
    if len(unique_candidates) != 1:
        return None
    return unique_candidates.pop()


def resolve_winner_market(bet, event):
    return resolve_winner_market_text(bet.market, bet, event)


def resolve_winner_market_text(market_text, bet, event):
    selection = parse_winner_market_text(market_text, bet)
    if selection is None:
        return None
    scores = get_event_scores(bet, event)
    if scores is None:
        return None
    home_score, away_score = scores
    if home_score == away_score:
        result = 'draw'
    elif home_score > away_score:
        result = 'home'
    else:
        result = 'away'
    return SettlementDecision(
        status=Bet.Status.WON if selection == result else Bet.Status.LOST,
        reason=f'Placar final {home_score}x{away_score}',
    )


def resolve_bet_from_event(bet, event):
    if not event.get('completed'):
        return None
    if not bet.external_event_id or event.get('id') != bet.external_event_id:
        return None
    if market_has_multiple_intents(bet.market):
        return None
    return resolve_total_market(bet, event) or resolve_winner_market(bet, event)


def resolve_surebet_entry_from_event(entry, bet, event):
    if market_has_multiple_intents(entry.label):
        return None
    return resolve_total_market_text(entry.label, bet, event) or resolve_winner_market_text(
        entry.label,
        bet,
        event,
    )


def resolve_surebet_from_event(bet, event):
    if not event.get('completed'):
        return None
    if not bet.external_event_id or event.get('id') != bet.external_event_id:
        return None
    if bet.strategy != 'Surebet':
        return None

    entries = list(bet.surebet_entries.all())
    if len(entries) < 2:
        return None

    decisions = []
    for entry in entries:
        decision = resolve_surebet_entry_from_event(entry, bet, event)
        if decision is None:
            return None
        decisions.append((entry, decision))

    winners = [entry for entry, decision in decisions if decision.status == Bet.Status.WON]
    if len(winners) != 1:
        return None
    winner = winners[0]
    return SettlementDecision(
        status=Bet.Status.WON if winner.net_result >= 0 else Bet.Status.LOST,
        reason=f'{winner.bookmaker} - {winner.label}',
    ), winner


def apply_settlement(bet, decision):
    bet.status = decision.status
    bet.actual_net_result = bet.potential_profit if decision.status == Bet.Status.WON else -bet.stake
    note = f'Fechada automaticamente. {decision.reason}.'
    bet.notes = f'{bet.notes}\n{note}'.strip() if bet.notes else note
    bet.save(update_fields=['status', 'actual_net_result', 'notes'])
    return bet


def settlement_transaction_kind(amount):
    return (
        BankrollTransaction.Kind.DEPOSIT
        if amount >= 0 else BankrollTransaction.Kind.WITHDRAW
    )


def create_protection_balance_movements(bet, entries, winner):
    bet.bankroll_transactions.all().delete()
    entry_amounts = [
        (entry, entry.settlement_result_for(winner))
        for entry in entries
        if entry.bankroll_id
    ]
    total_movement = sum((amount for _entry, amount in entry_amounts), start=Decimal('0.00'))
    manual_delta = (winner.net_result - total_movement).quantize(Decimal('0.01'))
    for entry in entries:
        if not entry.bankroll_id:
            continue
        amount = entry.settlement_result_for(winner)
        if entry.pk == winner.pk and manual_delta:
            amount = (amount + manual_delta).quantize(Decimal('0.01'))
        if amount == 0:
            continue
        BankrollTransaction.objects.create(
            bankroll=entry.bankroll,
            bet=bet,
            kind=settlement_transaction_kind(amount),
            amount=abs(amount).quantize(Decimal('0.01')),
            note=(
                f'{bet.strategy}: {entry.label} '
                f'({"vencedora" if entry.pk == winner.pk else "perdedora"})'
            )[:160],
        )


def apply_surebet_settlement(bet, decision, winner):
    with transaction.atomic():
        bet.surebet_entries.update(is_winner=False)
        winner.is_winner = True
        winner.save(update_fields=['is_winner'])
        bet.actual_net_result = winner.net_result
        bet.status = decision.status
        bet.exact_score = f'{winner.bookmaker} - {winner.label}'[:40]
        note = f'Fechada automaticamente. Vencedora: {decision.reason}.'
        bet.notes = f'{bet.notes}\n{note}'.strip() if bet.notes else note
        bet.save(update_fields=['actual_net_result', 'status', 'exact_score', 'notes'])
        entries = bet.surebet_entries.select_related('bankroll').all()
        create_protection_balance_movements(bet, entries, winner)

        if winner.freebet_enabled and winner.freebet_amount > 0:
            FreeBet.objects.get_or_create(
                source_bet=bet,
                bookmaker=winner.bookmaker,
                amount=winner.freebet_amount,
                defaults={},
            )
    return bet
