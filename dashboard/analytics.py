from collections import defaultdict
from calendar import monthrange
from decimal import Decimal

from django.utils import timezone

from .models import Bet


def calculate_roi(profit, stake):
    if not stake:
        return Decimal('0.00')
    return profit / stake * Decimal('100')


def settled_bets(bets):
    return [bet for bet in bets if bet.status != Bet.Status.OPEN]


def bet_accounting_at(bet):
    return bet.accounting_at


def period_start(days=None, month=False, reference_date=None):
    now = reference_date or timezone.localtime()
    if month:
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if days is None:
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    return now - timezone.timedelta(days=days)


def result_for_period(bets, start):
    period_bets = [
        bet
        for bet in settled_bets(bets)
        if timezone.localtime(bet_accounting_at(bet)) >= start
    ]
    profit = sum((bet.net_result for bet in period_bets), start=Decimal('0.00'))
    stake = sum((bet.stake for bet in period_bets), start=Decimal('0.00'))
    return {
        'profit': profit,
        'stake': stake,
        'roi': calculate_roi(profit, stake),
        'count': len(period_bets),
    }


def grouped_roi(bets, key_func):
    groups = defaultdict(list)
    for bet in settled_bets(bets):
        groups[key_func(bet)].append(bet)

    rows = []
    for label, group_bets in groups.items():
        stake = sum((bet.stake for bet in group_bets), start=Decimal('0.00'))
        profit = sum((bet.net_result for bet in group_bets), start=Decimal('0.00'))
        wins = sum(1 for bet in group_bets if bet.status == Bet.Status.WON)
        rows.append(
            {
                'label': label,
                'stake': stake,
                'profit': profit,
                'roi': calculate_roi(profit, stake),
                'count': len(group_bets),
                'win_rate': wins / len(group_bets) * 100 if group_bets else 0,
            }
        )

    return sorted(rows, key=lambda row: row['profit'], reverse=True)


def equity_curve(bets, initial_balance):
    values = [float(initial_balance)]
    running_total = Decimal(initial_balance)
    for bet in sorted(settled_bets(bets), key=bet_accounting_at):
        running_total += bet.net_result
        values.append(float(running_total))
    return values


def max_drawdown(values):
    peak = values[0] if values else 0
    worst = 0
    for value in values:
        peak = max(peak, value)
        drawdown = value - peak
        worst = min(worst, drawdown)
    return Decimal(str(worst)).quantize(Decimal('0.01'))


def current_streak(bets):
    ordered = sorted(settled_bets(bets), key=bet_accounting_at, reverse=True)
    if not ordered:
        return {'label': 'Sem sequência', 'count': 0, 'kind': 'neutral'}

    first_status = ordered[0].status
    count = 0
    for bet in ordered:
        if bet.status != first_status:
            break
        count += 1

    return {
        'label': 'Vitorias' if first_status == Bet.Status.WON else 'Derrotas',
        'count': count,
        'kind': 'positive' if first_status == Bet.Status.WON else 'negative',
    }


def build_month_calendar(bets, reference_date=None):
    current_date = reference_date or timezone.localdate()
    month_start = current_date.replace(day=1)
    _, days_in_month = monthrange(current_date.year, current_date.month)
    first_weekday = month_start.weekday()

    daily_results = defaultdict(lambda: {'profit': Decimal('0.00'), 'count': 0})
    for bet in settled_bets(bets):
        bet_date = timezone.localtime(bet_accounting_at(bet)).date()
        if bet_date.year == current_date.year and bet_date.month == current_date.month:
            daily_results[bet_date]['profit'] += bet.net_result
            daily_results[bet_date]['count'] += 1

    days = []
    for _ in range(first_weekday):
        days.append({'in_month': False})

    today = timezone.localdate()
    for day in range(1, days_in_month + 1):
        date = month_start.replace(day=day)
        result = daily_results[date]
        profit = result['profit'].quantize(Decimal('0.01'))
        if profit > 0:
            tone = 'positive'
        elif profit < 0:
            tone = 'negative'
        else:
            tone = 'neutral'

        days.append(
            {
                'date': date,
                'day': day,
                'profit': profit,
                'count': result['count'],
                'tone': tone,
                'in_month': True,
                'is_today': date == today,
            }
        )

    while len(days) % 7:
        days.append({'in_month': False})

    weeks = [days[index:index + 7] for index in range(0, len(days), 7)]
    month_profit = sum((day['profit'] for day in days if day.get('in_month')), Decimal('0.00'))
    month_count = sum((day['count'] for day in days if day.get('in_month')), 0)

    return {
        'label': month_start.strftime('%m/%Y'),
        'weeks': weeks,
        'weekdays': ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab', 'Dom'],
        'profit': month_profit.quantize(Decimal('0.01')),
        'count': month_count,
    }


def period_chart_for_month(bets, reference_date):
    current_date = reference_date or timezone.localdate()
    _, days_in_month = monthrange(current_date.year, current_date.month)
    monthly_results = defaultdict(Decimal)
    for bet in settled_bets(bets):
        bet_date = timezone.localtime(bet_accounting_at(bet)).date()
        if bet_date.year == current_date.year and bet_date.month == current_date.month:
            monthly_results[bet_date.day] += bet.net_result

    values = []
    labels = []

    for day in range(1, days_in_month + 1):
        labels.append(str(day))
        values.append(float(monthly_results[day].quantize(Decimal('0.01'))))

    return labels, values


def build_analytics(bets, initial_balance, reference_date=None):
    bet_list = list(bets)
    today = result_for_period(bet_list, period_start(reference_date=None))
    week = result_for_period(bet_list, period_start(days=7, reference_date=None))
    month = result_for_period(bet_list, period_start(month=True, reference_date=None))
    curve = equity_curve(bet_list, initial_balance)
    market_rows = grouped_roi(bet_list, lambda bet: bet.market)
    bankroll_rows = grouped_roi(
        bet_list,
        lambda bet: bet.bankroll.name if bet.bankroll else bet.entity.name if bet.entity else 'Sem origem',
    )
    sport_rows = grouped_roi(bet_list, lambda bet: bet.sport or 'Sem esporte')
    period_labels, period_chart = period_chart_for_month(bet_list, reference_date or timezone.localdate())

    return {
        'periods': [
            {'label': 'Hoje', **today},
            {'label': '7 dias', **week},
            {'label': 'Mês atual', **month},
        ],
        'market_rows': market_rows,
        'bankroll_rows': bankroll_rows,
        'sport_rows': sport_rows,
        'best_market': market_rows[0] if market_rows else None,
        'worst_market': market_rows[-1] if market_rows else None,
        'best_sport': sport_rows[0] if sport_rows else None,
        'worst_sport': sport_rows[-1] if sport_rows else None,
        'best_bankroll': bankroll_rows[0] if bankroll_rows else None,
        'worst_bankroll': bankroll_rows[-1] if bankroll_rows else None,
        'equity_curve': curve,
        'drawdown': max_drawdown(curve),
        'streak': current_streak(bet_list),
        'period_chart': period_chart,
        'period_labels': period_labels,
        'month_calendar': build_month_calendar(bet_list, reference_date),
    }
