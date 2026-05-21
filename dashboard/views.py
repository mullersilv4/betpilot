from decimal import Decimal
from decimal import InvalidOperation
import os

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import ensure_csrf_cookie
from django.db import transaction
from django.db.models import Q
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render

from .analytics import build_analytics
from .automation import import_bets_from_csv
from .automation import import_bets_from_text
from .forms import BankrollForm
from .forms import BankrollTransactionForm
from .forms import BetFilterForm
from .forms import BetForm
from .forms import EntityForm
from .forms import ImportTextForm
from .forms import MonthlyGoalForm
from .forms import OddsSearchForm
from .forms import SignUpForm
from .forms import TransferForm
from .models import Bankroll
from .models import BankrollTransaction
from .models import Bet
from .models import Entity
from .models import FreeBet
from .models import MonthlyGoal
from .models import SureBetEntry
from .odds_api import OddsApiClient
from .odds_api import OddsApiError
from .odds_api import build_odds_comparison
from .odds_api import detect_surebets


MONTH_CHOICES = [
    (1, 'Janeiro'),
    (2, 'Fevereiro'),
    (3, 'Marco'),
    (4, 'Abril'),
    (5, 'Maio'),
    (6, 'Junho'),
    (7, 'Julho'),
    (8, 'Agosto'),
    (9, 'Setembro'),
    (10, 'Outubro'),
    (11, 'Novembro'),
    (12, 'Dezembro'),
]

ODDS_CACHE_TIMEOUT = 60 * 15
EVENT_SEARCH_CACHE_TIMEOUT = 60 * 20


def apply_bet_filters(bets, form):
    if not form.is_valid():
        return bets

    bankroll = form.cleaned_data.get('bankroll')
    status = form.cleaned_data.get('status')
    entry_type = form.cleaned_data.get('entry_type')
    sport = form.cleaned_data.get('sport')
    competition = form.cleaned_data.get('competition')
    strategy = form.cleaned_data.get('strategy')
    market = form.cleaned_data.get('market')
    query = form.cleaned_data.get('query')
    min_odds = form.cleaned_data.get('min_odds')
    max_odds = form.cleaned_data.get('max_odds')

    if bankroll:
        bets = bets.filter(bankroll=bankroll)
    if status:
        bets = bets.filter(status=status)
    if entry_type:
        bets = bets.filter(entry_type=entry_type)
    if sport:
        bets = bets.filter(sport__icontains=sport)
    if competition:
        bets = bets.filter(competition__icontains=competition)
    if strategy:
        bets = bets.filter(strategy__icontains=strategy)
    if market:
        bets = bets.filter(market__icontains=market)
    if query:
        bets = bets.filter(
            Q(game__icontains=query)
            | Q(market__icontains=query)
            | Q(competition__icontains=query)
            | Q(strategy__icontains=query)
            | Q(notes__icontains=query)
        )
    if min_odds:
        bets = bets.filter(odds__gte=min_odds)
    if max_odds:
        bets = bets.filter(odds__lte=max_odds)

    return bets


def dashboard_period(request, bets):
    today = timezone.localdate()
    year = today.year
    month = today.month

    try:
        requested_year = int(request.GET.get('dashboard_year', year))
        requested_month = int(request.GET.get('dashboard_month', month))
    except (TypeError, ValueError):
        requested_year = year
        requested_month = month

    if 1 <= requested_month <= 12:
        month = requested_month
    if 2000 <= requested_year <= today.year + 1:
        year = requested_year

    years = {today.year, year}
    for bet in bets:
        years.add(timezone.localtime(bet.created_at).year)

    reference_date = timezone.datetime(
        year,
        month,
        1,
        tzinfo=timezone.get_current_timezone(),
    )
    next_month = (
        timezone.datetime(year + 1, 1, 1, tzinfo=timezone.get_current_timezone())
        if month == 12
        else timezone.datetime(year, month + 1, 1, tzinfo=timezone.get_current_timezone())
    )

    return {
        'year': year,
        'month': month,
        'reference_date': reference_date,
        'next_month': next_month,
        'month_choices': MONTH_CHOICES,
        'year_choices': sorted(years, reverse=True),
    }


def parse_import_lines(raw_text):
    bankroll = Bankroll.objects.filter(owner__isnull=False).first() or Bankroll.objects.first()
    if bankroll is None:
        return [], ['Nenhuma banca cadastrada.']
    user = bankroll.owner
    if user is None:
        from django.contrib.auth.models import User

        user, _ = User.objects.get_or_create(username='legacy')
        Bankroll.objects.filter(owner__isnull=True).update(owner=user)
    imported, errors, _warnings = import_bets_from_text(raw_text, user)
    return imported, errors


def build_dashboard_context(request, **forms):
    entities = Entity.objects.filter(owner=request.user).prefetch_related('bankrolls')
    bankrolls = Bankroll.objects.filter(owner=request.user).select_related('entity').prefetch_related('bets', 'transactions')
    all_bets = user_bets(request.user).select_related('bankroll', 'bankroll__entity', 'entity')
    all_bet_list = list(all_bets)
    dashboard_filter = dashboard_period(request, all_bet_list)
    dashboard_bets = [
        bet
        for bet in all_bet_list
        if dashboard_filter['reference_date'] <= timezone.localtime(bet.created_at) < dashboard_filter['next_month']
    ]
    filter_form = forms.get('filter_form') or BetFilterForm(request.GET or None, user=request.user)
    bets = apply_bet_filters(all_bets, filter_form)

    settled_bets = [bet for bet in dashboard_bets if bet.status != Bet.Status.OPEN]
    total_stake = sum((bet.stake for bet in dashboard_bets), start=Decimal('0.00'))
    net_profit = sum((bet.net_result for bet in dashboard_bets), start=Decimal('0.00'))
    won_bets = sum(1 for bet in dashboard_bets if bet.status == Bet.Status.WON)
    open_exposure = sum(
        (bet.stake for bet in dashboard_bets if bet.status == Bet.Status.OPEN),
        start=Decimal('0.00'),
    )
    open_bet_count = sum(1 for bet in dashboard_bets if bet.status == Bet.Status.OPEN)
    available_freebets = FreeBet.objects.filter(
        Q(source_bet__bankroll__owner=request.user) | Q(source_bet__entity__owner=request.user),
        is_used=False,
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_initial_balance = sum(
        (bankroll.initial_balance for bankroll in bankrolls),
        start=Decimal('0.00'),
    )
    total_current_balance = sum(
        (bankroll.current_balance for bankroll in bankrolls),
        start=Decimal('0.00'),
    )
    total_available_balance = sum(
        (bankroll.available_balance for bankroll in bankrolls),
        start=Decimal('0.00'),
    )
    roi = (net_profit / total_stake * 100) if total_stake else Decimal('0.00')
    win_rate = (won_bets / len(settled_bets) * 100) if settled_bets else 0

    market_stats = []
    for market in sorted({bet.market for bet in all_bets}):
        market_bets = [bet for bet in all_bets if bet.market == market]
        market_stake = sum((bet.stake for bet in market_bets), start=Decimal('0.00'))
        market_profit = sum((bet.net_result for bet in market_bets), start=Decimal('0.00'))
        market_roi = (market_profit / market_stake * 100) if market_stake else 0
        market_stats.append(
            {
                'label': market,
                'roi': market_roi,
                'volume': len(market_bets),
                'bar_width': min(abs(float(market_roi)) * 3, 100),
            }
        )

    balance_before_period = total_initial_balance + sum(
        (
            bet.net_result
            for bet in all_bet_list
            if bet.status != Bet.Status.OPEN
            and timezone.localtime(bet.created_at) < dashboard_filter['reference_date']
        ),
        start=Decimal('0.00'),
    )
    running_total = float(balance_before_period)
    chart_values = [round(running_total, 2)]
    for bet in sorted(settled_bets, key=lambda item: item.created_at):
        running_total += float(bet.net_result)
        chart_values.append(round(running_total, 2))

    latest_transactions = BankrollTransaction.objects.filter(
        bankroll__owner=request.user
    ).select_related('bankroll')[:8]
    analytics = build_analytics(
        dashboard_bets,
        balance_before_period,
        dashboard_filter['reference_date'].date(),
    )

    return {
        'bankroll_form': forms.get('bankroll_form') or BankrollForm(user=request.user),
        'entity_form': forms.get('entity_form') or EntityForm(user=request.user),
        'form': forms.get('bet_form') or BetForm(user=request.user),
        'transaction_form': forms.get('transaction_form') or BankrollTransactionForm(user=request.user),
        'transfer_form': forms.get('transfer_form') or TransferForm(user=request.user),
        'filter_form': filter_form,
        'import_form': forms.get('import_form') or ImportTextForm(),
        'odds_form': forms.get('odds_form') or OddsSearchForm(),
        'odds_opportunities': forms.get('odds_opportunities') or [],
        'odds_comparisons': forms.get('odds_comparisons') or [],
        'odds_searched': forms.get('odds_searched') or False,
        'goal_form': forms.get('goal_form') or MonthlyGoalForm(user=request.user),
        'surebet_errors': forms.get('surebet_errors') or [],
        'surebet_data': forms.get('surebet_data') or {},
        'surebet_rows': build_surebet_rows(forms.get('surebet_data')),
        'bankrolls': bankrolls,
        'entities': entities,
        'bets': bets[:30],
        'latest_transactions': latest_transactions,
        'monthly_goals': MonthlyGoal.objects.filter(bankroll__owner=request.user).select_related('bankroll')[:12],
        'dashboard_filter': dashboard_filter,
        'metrics': {
            'total_stake': total_stake,
            'net_profit': net_profit,
            'roi': roi,
            'win_rate': win_rate,
            'open_exposure': open_exposure,
            'open_bet_count': open_bet_count,
            'bet_count': all_bets.count(),
            'total_initial_balance': total_initial_balance,
            'total_current_balance': total_current_balance,
            'total_available_balance': total_available_balance,
            'available_freebets': available_freebets,
        },
        'market_stats': market_stats[:5],
        'chart_values': chart_values,
        'analytics': analytics,
    }


def decimal_from_post(post_data, field_name, default='0'):
    raw_value = (post_data.get(field_name) or default).replace(',', '.').strip()
    try:
        return Decimal(raw_value)
    except InvalidOperation:
        return None


def surebet_indices_from_post(post_data):
    indices = set()
    for key in post_data.keys():
        if not key.startswith('surebet_'):
            continue
        suffix = key.rsplit('_', 1)[-1]
        if suffix.isdigit():
            indices.add(int(suffix))
    entry_count = decimal_from_post(post_data, 'surebet_entry_count')
    if entry_count:
        indices.update(range(1, int(entry_count) + 1))
    return sorted(indices or {1, 2, 3})


def build_surebet_rows(post_data=None):
    indices = surebet_indices_from_post(post_data) if post_data else [1, 2, 3]
    rows = []
    for index in indices:
        rows.append(
            {
                'index': index,
                'bookmaker': (post_data.get(f'surebet_bookmaker_{index}') if post_data else '') or '',
                'outcome': (post_data.get(f'surebet_outcome_{index}') if post_data else '') or '',
                'odd': (post_data.get(f'surebet_odd_{index}') if post_data else '') or '',
                'stake': (post_data.get(f'surebet_stake_{index}') if post_data else '') or '',
                'commission': (post_data.get(f'surebet_commission_{index}') if post_data else '') or '',
                'cashback': (post_data.get(f'surebet_cashback_{index}') if post_data else '') or '',
                'boost': (post_data.get(f'surebet_boost_{index}') if post_data else '') or '',
                'freebet_enabled': (post_data.get(f'surebet_freebet_enabled_{index}') if post_data else '') or '',
                'freebet_amount': (post_data.get(f'surebet_freebet_amount_{index}') if post_data else '') or '',
                'optional': index > 2,
                'readonly': index > 1,
            }
        )
    return rows


def build_surebet_payload(post_data):
    outcomes = []
    target_return = None
    for index in surebet_indices_from_post(post_data):
        bookmaker = (post_data.get(f'surebet_bookmaker_{index}') or '').strip()
        label = (post_data.get(f'surebet_outcome_{index}') or '').strip()
        odd = decimal_from_post(post_data, f'surebet_odd_{index}')
        stake = decimal_from_post(post_data, f'surebet_stake_{index}')
        commission = decimal_from_post(post_data, f'surebet_commission_{index}')
        cashback = decimal_from_post(post_data, f'surebet_cashback_{index}')
        boost = decimal_from_post(post_data, f'surebet_boost_{index}')
        freebet_enabled = post_data.get(f'surebet_freebet_enabled_{index}') == '1'
        freebet_amount = decimal_from_post(post_data, f'surebet_freebet_amount_{index}')
        if (
            not bookmaker
            and not label
            and (not odd or odd == 0)
            and (not stake or stake == 0)
            and (not commission or commission == 0)
            and (not cashback or cashback == 0)
            and (not boost or boost == 0)
            and not freebet_enabled
            and (not freebet_amount or freebet_amount == 0)
        ):
            continue
        commission = commission or Decimal('0.00')
        cashback = cashback or Decimal('0.00')
        boost = boost or Decimal('0.00')
        freebet_amount = freebet_amount or Decimal('0.00')
        effective_odd = odd * (Decimal('1.00') + boost / Decimal('100')) if odd else None
        payout_multiplier = None
        if effective_odd and effective_odd > 1:
            payout_multiplier = Decimal('1.00') + (
                (effective_odd - Decimal('1.00'))
                * (Decimal('1.00') - commission / Decimal('100'))
            )
        if index == 1 and odd and odd > 1 and stake and stake > 0:
            target_return = (stake * payout_multiplier).quantize(Decimal('0.01'))
        elif target_return and payout_multiplier and payout_multiplier > 0:
            stake = (target_return / payout_multiplier).quantize(Decimal('0.01'))
        outcomes.append(
            {
                'bookmaker': bookmaker,
                'label': label or f'Resultado {index}',
                'odd': odd,
                'stake': stake,
                'commission': commission,
                'cashback': cashback,
                'boost': boost,
                'freebet_enabled': freebet_enabled,
                'freebet_amount': freebet_amount,
                'effective_odd': effective_odd,
                'payout_multiplier': payout_multiplier,
            }
        )
    return outcomes


def format_money(value):
    return f'R$ {value.quantize(Decimal("0.01"))}'


def add_suggested_stakes(opportunities, total_stake):
    enriched = []
    total_stake = Decimal(total_stake)
    for opportunity in opportunities:
        implied = Decimal(str(opportunity['implied_probability'])) / Decimal('100')
        expected_return = total_stake / implied if implied else Decimal('0.00')
        outcomes = []
        for outcome in opportunity['outcomes']:
            price = Decimal(str(outcome['price']))
            outcomes.append(
                {
                    **outcome,
                    'suggested_stake': (expected_return / price).quantize(Decimal('0.01')),
                }
            )
        enriched.append(
            {
                **opportunity,
                'total_stake': total_stake.quantize(Decimal('0.01')),
                'expected_return': expected_return.quantize(Decimal('0.01')),
                'outcomes': outcomes,
            }
        )
    return enriched


def guess_event_sports(sport_text, competition_text):
    text = f'{sport_text or ""} {competition_text or ""}'.lower()
    choices = dict(OddsSearchForm.SPORT_CHOICES)
    exact_matches = [
        key
        for key, label in choices.items()
        if any(part and part in text for part in label.lower().replace('-', ' ').split())
    ]

    if 'brasil' in text or 'brasileir' in text:
        return ['soccer_brazil_campeonato']
    if 'champions' in text:
        return ['soccer_uefa_champs_league']
    if 'premier' in text or 'epl' in text:
        return ['soccer_epl']
    if 'liga' in text or 'la liga' in text:
        return ['soccer_spain_la_liga']
    if 'serie a' in text or 'italia' in text:
        return ['soccer_italy_serie_a']
    if 'bundesliga' in text or 'alem' in text:
        return ['soccer_germany_bundesliga']
    if 'ligue' in text or 'franca' in text:
        return ['soccer_france_ligue_one']
    if 'nba' in text or 'basquete' in text or 'basket' in text:
        return ['basketball_nba']
    if 'nfl' in text or 'americano' in text:
        return ['americanfootball_nfl']
    if exact_matches:
        return exact_matches[:3]
    if 'futebol' in text or 'soccer' in text:
        return ['soccer_brazil_campeonato', 'soccer_epl', 'soccer_uefa_champs_league']
    return ['soccer_brazil_campeonato']


def normalize_event(event):
    home_team = event.get('home_team') or ''
    away_team = event.get('away_team') or ''
    commence_time = event.get('commence_time') or ''
    starts_at = parse_datetime(commence_time) if commence_time else None
    local_starts_at = timezone.localtime(starts_at) if starts_at else None
    return {
        'id': event.get('id'),
        'game': f'{home_team} x {away_team}'.strip(' x'),
        'home_team': home_team,
        'away_team': away_team,
        'competition': event.get('sport_title') or '',
        'sport': 'Futebol' if (event.get('sport_key') or '').startswith('soccer') else event.get('sport_title') or '',
        'event_date': local_starts_at.strftime('%Y-%m-%dT%H:%M') if local_starts_at else '',
        'display_date': local_starts_at.strftime('%d/%m/%Y %H:%M') if local_starts_at else '',
    }


def user_bets(user):
    return Bet.objects.filter(Q(bankroll__owner=user) | Q(entity__owner=user)).distinct()


@login_required
def event_autocomplete(request):
    api_key = os.environ.get('THE_ODDS_API_KEY')
    query = (request.GET.get('q') or '').strip().lower()
    sport_text = request.GET.get('sport') or ''
    competition_text = request.GET.get('competition') or ''

    if not api_key:
        return JsonResponse({'results': [], 'error': 'API key nao configurada.'}, status=503)

    sport_keys = guess_event_sports(sport_text, competition_text)
    client = OddsApiClient(api_key)
    events = []

    for sport_key in sport_keys:
        cache_key = f'events:{sport_key}'
        sport_events = cache.get(cache_key)
        if sport_events is None:
            try:
                sport_events = client.events(sport_key)
            except OddsApiError:
                sport_events = []
            cache.set(cache_key, sport_events, EVENT_SEARCH_CACHE_TIMEOUT)
        events.extend({**event, 'sport_key': sport_key} for event in sport_events)

    normalized = [normalize_event(event) for event in events]
    if query:
        normalized = [
            event
            for event in normalized
            if query in event['game'].lower() or query in event['competition'].lower()
        ]

    normalized = [event for event in normalized if event['game']]
    normalized.sort(key=lambda item: item['event_date'] or '9999')
    return JsonResponse({'results': normalized[:12]})


@login_required
def index(request):
    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'bankroll':
            bankroll_form = BankrollForm(request.POST, user=request.user)
            if bankroll_form.is_valid():
                bankroll = bankroll_form.save(commit=False)
                bankroll.owner = request.user
                bankroll.save()
                messages.success(request, 'Banca cadastrada com sucesso.')
                return redirect('dashboard:index')
            context = build_dashboard_context(request, bankroll_form=bankroll_form)
            return render(request, 'dashboard/index.html', context)

        if form_type == 'entity':
            entity_form = EntityForm(request.POST, user=request.user)
            if entity_form.is_valid():
                entity = entity_form.save(commit=False)
                entity.owner = request.user
                entity.save()
                messages.success(request, 'Entidade cadastrada com sucesso.')
                return redirect('dashboard:index')
            context = build_dashboard_context(request, entity_form=entity_form)
            return render(request, 'dashboard/index.html', context)

        if form_type == 'transaction':
            transaction_form = BankrollTransactionForm(request.POST, user=request.user)
            if transaction_form.is_valid():
                transaction_form.save()
                messages.success(request, 'Movimentacao registrada.')
                return redirect('dashboard:index')
            context = build_dashboard_context(request, transaction_form=transaction_form)
            return render(request, 'dashboard/index.html', context)

        if form_type == 'transfer':
            transfer_form = TransferForm(request.POST, user=request.user)
            if transfer_form.is_valid():
                source = transfer_form.cleaned_data['source']
                target = transfer_form.cleaned_data['target']
                amount = transfer_form.cleaned_data['amount']
                with transaction.atomic():
                    BankrollTransaction.objects.create(
                        bankroll=source,
                        kind=BankrollTransaction.Kind.TRANSFER_OUT,
                        amount=amount,
                        note=f'Transferencia para {target.name}',
                    )
                    BankrollTransaction.objects.create(
                        bankroll=target,
                        kind=BankrollTransaction.Kind.TRANSFER_IN,
                        amount=amount,
                        note=f'Transferencia de {source.name}',
                    )
                messages.success(request, 'Transferencia registrada.')
                return redirect('dashboard:index')
            context = build_dashboard_context(request, transfer_form=transfer_form)
            return render(request, 'dashboard/index.html', context)

        if form_type == 'import':
            import_form = ImportTextForm(request.POST, request.FILES)
            if import_form.is_valid():
                if import_form.cleaned_data.get('csv_file'):
                    imported, errors, warnings = import_bets_from_csv(
                        import_form.cleaned_data['csv_file'], request.user
                    )
                else:
                    imported, errors, warnings = import_bets_from_text(
                        import_form.cleaned_data['raw_text'], request.user
                    )
                if imported:
                    messages.success(request, f'{len(imported)} aposta(s) importada(s).')
                for warning in warnings:
                    messages.warning(request, warning)
                for error in errors:
                    messages.error(request, error)
                return redirect('dashboard:index')
            context = build_dashboard_context(request, import_form=import_form)
            return render(request, 'dashboard/index.html', context)

        if form_type == 'odds_search':
            odds_form = OddsSearchForm(request.POST)
            odds_opportunities = []
            odds_comparisons = []
            if odds_form.is_valid():
                api_key = os.environ.get('THE_ODDS_API_KEY')
                if not api_key:
                    messages.error(
                        request,
                        'Defina THE_ODDS_API_KEY no ambiente para buscar odds.',
                    )
                else:
                    client = OddsApiClient(api_key=api_key)
                    try:
                        cache_key = (
                            'odds_api:h2h:'
                            f'{odds_form.cleaned_data["sport"]}:'
                            f'{odds_form.cleaned_data["regions"]}:'
                            f'{odds_form.cleaned_data["bookmakers"]}:'
                            f'{odds_form.cleaned_data["brazil_regulated_only"]}'
                        )
                        events = cache.get(cache_key)
                        used_cache = events is not None
                        if events is None:
                            events = client.odds(
                                sport_key=odds_form.cleaned_data['sport'],
                                regions=odds_form.cleaned_data['regions'],
                                markets='h2h',
                                bookmakers=odds_form.cleaned_data['bookmakers'],
                            )
                            cache.set(cache_key, events, ODDS_CACHE_TIMEOUT)
                        odds_opportunities = detect_surebets(
                            events,
                            limit=odds_form.cleaned_data['limit'],
                            brazil_regulated_only=odds_form.cleaned_data[
                                'brazil_regulated_only'
                            ],
                        )
                        odds_comparisons = build_odds_comparison(
                            events,
                            limit=odds_form.cleaned_data['limit'],
                            brazil_regulated_only=odds_form.cleaned_data[
                                'brazil_regulated_only'
                            ],
                        )
                        odds_opportunities = add_suggested_stakes(
                            odds_opportunities,
                            odds_form.cleaned_data['stake'],
                        )
                    except OddsApiError as error:
                        messages.error(request, str(error))
                    else:
                        if odds_opportunities:
                            messages.success(
                                request,
                                (
                                    f'{len(odds_opportunities)} oportunidade(s) encontrada(s).'
                                    + (' Resultado vindo do cache.' if used_cache else '')
                                ),
                            )
                        else:
                            messages.warning(
                                request,
                                (
                                    'Nenhuma surebet encontrada para esses filtros.'
                                    + (' Resultado vindo do cache.' if used_cache else '')
                                ),
                            )
            context = build_dashboard_context(
                request,
                odds_form=odds_form,
                odds_opportunities=odds_opportunities,
                odds_comparisons=odds_comparisons,
                odds_searched=True,
            )
            return render(request, 'dashboard/index.html', context)

        if form_type == 'goal':
            goal_form = MonthlyGoalForm(request.POST, user=request.user)
            if goal_form.is_valid():
                goal_form.save()
                messages.success(request, 'Meta mensal salva.')
                return redirect('dashboard:index')
            context = build_dashboard_context(request, goal_form=goal_form)
            return render(request, 'dashboard/index.html', context)

        if form_type == 'surebet':
            surebet_errors = []
            entity_id = request.POST.get('surebet_entity')
            entity = None
            if entity_id:
                entity = Entity.objects.filter(pk=entity_id, owner=request.user).first()
            outcomes = build_surebet_payload(request.POST)
            game = (request.POST.get('surebet_game') or '').strip()
            sport = (request.POST.get('surebet_sport') or 'Futebol').strip()
            competition = (request.POST.get('surebet_competition') or '').strip()
            game_link = (request.POST.get('surebet_game_link') or '').strip()
            notes = (request.POST.get('surebet_notes') or '').strip()

            if entity is None:
                surebet_errors.append('Selecione uma entidade valida.')
            if not game:
                surebet_errors.append('Informe o jogo da surebet.')
            if len(outcomes) < 2:
                surebet_errors.append('Informe pelo menos dois resultados protegidos.')

            for outcome in outcomes:
                if not outcome['bookmaker']:
                    surebet_errors.append(f'Informe a casa de aposta de {outcome["label"]}.')
                if outcome['odd'] is None or outcome['odd'] <= 1:
                    surebet_errors.append(f'A odd de {outcome["label"]} precisa ser maior que 1.00.')
                if outcome['stake'] is None or outcome['stake'] <= 0:
                    surebet_errors.append(f'O valor de {outcome["label"]} precisa ser maior que zero.')
                for field, label in [
                    ('commission', 'comissao'),
                    ('cashback', 'cashback'),
                    ('boost', 'aumento'),
                ]:
                    if outcome[field] < 0 or outcome[field] > 100:
                        surebet_errors.append(
                            f'O campo {label} de {outcome["label"]} precisa ficar entre 0% e 100%.'
                        )
                if outcome['freebet_enabled'] and outcome['freebet_amount'] <= 0:
                    surebet_errors.append(
                        f'Informe o valor da freebet gerada em {outcome["label"]}.'
                    )

            if not surebet_errors:
                total_stake = sum((outcome['stake'] for outcome in outcomes), start=Decimal('0.00'))
                outcome_results = [
                    {
                        **outcome,
                        'return': (
                            outcome['stake'] * outcome['payout_multiplier']
                        ).quantize(Decimal('0.01')),
                    }
                    for outcome in outcomes
                ]
                for outcome in outcome_results:
                    losing_cashback = sum(
                        (
                            other['stake'] * (other['cashback'] / Decimal('100'))
                            for other in outcome_results
                            if other is not outcome
                        ),
                        start=Decimal('0.00'),
                    )
                    outcome['cashback_return'] = losing_cashback.quantize(Decimal('0.01'))
                    outcome['net'] = (
                        outcome['return'] + outcome['cashback_return'] - total_stake
                    ).quantize(Decimal('0.01'))
                    outcome['effective_odd_display'] = outcome['effective_odd'].quantize(Decimal('0.01'))

            if surebet_errors:
                context = build_dashboard_context(
                    request,
                    surebet_errors=surebet_errors,
                    surebet_data=request.POST,
                )
                return render(request, 'dashboard/index.html', context)

            best_return = max((outcome['return'] for outcome in outcome_results), default=total_stake)
            effective_odd = (best_return / total_stake).quantize(Decimal('0.01'))
            market = 'Surebet: ' + ' / '.join(outcome['label'] for outcome in outcome_results)
            protection_lines = [
                'Surebet cadastrada com protecoes:',
                f'Investimento total: {format_money(total_stake)}',
            ]
            for outcome in outcome_results:
                protection_lines.append(
                    (
                        f'{outcome["bookmaker"]} - {outcome["label"]}: odd {outcome["odd"]}, '
                        f'comissao {outcome["commission"]}%, cashback {outcome["cashback"]}%, '
                        f'aumento {outcome["boost"]}%, '
                        f'aposta {format_money(outcome["stake"])}, '
                        f'retorno {format_money(outcome["return"])}, '
                        f'cashback no cenario {format_money(outcome["cashback_return"])}, '
                        f'resultado liquido {format_money(outcome["net"])}'
                        + (
                            f', gera freebet de {format_money(outcome["freebet_amount"])}'
                            if outcome['freebet_enabled'] else ''
                        )
                    )
                )
            if notes:
                protection_lines.extend(['Observacoes:', notes])

            bet = Bet.objects.create(
                bankroll=None,
                entity=entity,
                sport=sport,
                competition=competition,
                game=game,
                market=market[:120],
                strategy='Surebet',
                odds=effective_odd,
                stake=total_stake,
                exchange_commission=Decimal('0.00'),
                status=Bet.Status.OPEN,
                game_link=game_link,
                notes='\n'.join(protection_lines),
            )
            for outcome in outcome_results:
                SureBetEntry.objects.create(
                    bet=bet,
                    bookmaker=outcome['bookmaker'],
                    label=outcome['label'],
                    odds=outcome['odd'],
                    effective_odds=outcome['effective_odd_display'],
                    stake=outcome['stake'],
                    commission=outcome['commission'],
                    cashback=outcome['cashback'],
                    boost=outcome['boost'],
                    return_amount=outcome['return'],
                    cashback_return=outcome['cashback_return'],
                    net_result=outcome['net'],
                    freebet_enabled=outcome['freebet_enabled'],
                    freebet_amount=outcome['freebet_amount'],
                )
            messages.success(request, 'Surebet cadastrada com sucesso.')
            return redirect('dashboard:index')

        bet_form = BetForm(request.POST, user=request.user)
        if bet_form.is_valid():
            bet_form.save()
            messages.success(request, 'Aposta cadastrada com sucesso.')
            return redirect('dashboard:index')
        context = build_dashboard_context(request, bet_form=bet_form)
        return render(request, 'dashboard/index.html', context)

    return render(request, 'dashboard/index.html', build_dashboard_context(request))


@login_required
def edit_bet(request, pk):
    bet = get_object_or_404(user_bets(request.user), pk=pk)
    if request.method == 'POST':
        form = BetForm(request.POST, instance=bet, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Aposta atualizada.')
            return redirect('dashboard:index')
    else:
        form = BetForm(instance=bet, user=request.user)

    return render(request, 'dashboard/bet_form.html', {'form': form, 'bet': bet})


@login_required
def edit_bankroll(request, pk):
    bankroll = get_object_or_404(Bankroll, pk=pk, owner=request.user)
    if request.method == 'POST':
        form = BankrollForm(request.POST, instance=bankroll, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Configuracoes da banca atualizadas.')
            return redirect('dashboard:index')
    else:
        form = BankrollForm(instance=bankroll, user=request.user)

    return render(
        request,
        'dashboard/bankroll_form.html',
        {
            'form': form,
            'bankroll': bankroll,
        },
    )


@login_required
def delete_bankroll(request, pk):
    bankroll = get_object_or_404(Bankroll, pk=pk, owner=request.user)
    if request.method == 'POST':
        name = bankroll.name
        bet_count = bankroll.bets.count()
        with transaction.atomic():
            bankroll.bets.all().delete()
            bankroll.delete()
        if bet_count:
            messages.success(
                request,
                f'Banca "{name}" excluida com {bet_count} aposta(s) vinculada(s).',
            )
        else:
            messages.success(request, f'Banca "{name}" excluida com sucesso.')
    return redirect('dashboard:index')


@login_required
def delete_entity(request, pk):
    entity = get_object_or_404(Entity, pk=pk, owner=request.user)
    if request.method == 'POST':
        name = entity.name
        bankrolls = Bankroll.objects.filter(owner=request.user, entity=entity)
        bankroll_count = bankrolls.count()
        bet_count = Bet.objects.filter(Q(bankroll__in=bankrolls) | Q(entity=entity)).distinct().count()
        with transaction.atomic():
            Bet.objects.filter(Q(bankroll__in=bankrolls) | Q(entity=entity)).distinct().delete()
            bankrolls.delete()
            entity.delete()
        messages.success(
            request,
            (
                f'Entidade "{name}" excluida com {bankroll_count} banca(s) '
                f'e {bet_count} aposta(s) vinculada(s).'
            ),
        )
    return redirect('dashboard:index')


@login_required
def settle_bet(request, pk, status):
    bet = get_object_or_404(user_bets(request.user), pk=pk)
    if bet.strategy == 'Surebet':
        messages.error(request, 'Use a finalizacao da surebet para escolher a casa vencedora.')
        return redirect('dashboard:settle_surebet', pk=bet.pk)
    if request.method == 'POST' and status in {Bet.Status.WON, Bet.Status.LOST, Bet.Status.OPEN}:
        bet.status = status
        if status == Bet.Status.OPEN:
            bet.actual_net_result = None
            bet.save(update_fields=['status', 'actual_net_result'])
        else:
            bet.save(update_fields=['status'])
        messages.success(request, 'Status da aposta atualizado.')
    return redirect('dashboard:index')


@login_required
def settle_surebet(request, pk):
    bet = get_object_or_404(
        user_bets(request.user).prefetch_related('surebet_entries', 'generated_freebets'),
        pk=pk,
        strategy='Surebet',
    )
    entries = bet.surebet_entries.all()

    if request.method == 'POST':
        entry_id = request.POST.get('winner_entry')
        winner = entries.filter(pk=entry_id).first() if entry_id else None
        if winner is None:
            messages.error(request, 'Selecione a casa vencedora da surebet.')
            return render(
                request,
                'dashboard/surebet_settle.html',
                {'bet': bet, 'entries': entries},
            )

        with transaction.atomic():
            entries.update(is_winner=False)
            winner.is_winner = True
            winner.save(update_fields=['is_winner'])
            bet.actual_net_result = winner.net_result
            bet.status = Bet.Status.WON if winner.net_result >= 0 else Bet.Status.LOST
            bet.exact_score = f'{winner.bookmaker} - {winner.label}'[:40]
            bet.save(update_fields=['actual_net_result', 'status', 'exact_score'])

            if winner.freebet_enabled and winner.freebet_amount > 0:
                FreeBet.objects.get_or_create(
                    source_bet=bet,
                    bookmaker=winner.bookmaker,
                    amount=winner.freebet_amount,
                    defaults={},
                )

        messages.success(request, 'Surebet finalizada com o resultado da casa vencedora.')
        return redirect('dashboard:index')

    return render(
        request,
        'dashboard/surebet_settle.html',
        {'bet': bet, 'entries': entries},
    )


@login_required
def delete_bet(request, pk):
    bet = get_object_or_404(user_bets(request.user), pk=pk)
    if request.method == 'POST':
        bet.delete()
        messages.success(request, 'Aposta excluida.')
    return redirect('dashboard:index')


@login_required
def bankroll_detail(request, pk):
    bankroll = get_object_or_404(
        Bankroll.objects.prefetch_related('bets', 'transactions'),
        pk=pk,
        owner=request.user,
    )
    bets = bankroll.bets.select_related('bankroll')[:50]
    transactions = bankroll.transactions.all()[:50]
    goals = bankroll.goals.all()[:12]
    analytics = build_analytics(bankroll.bets.select_related('bankroll'), bankroll.initial_balance)

    return render(
        request,
        'dashboard/bankroll_detail.html',
        {
            'bankroll': bankroll,
            'bets': bets,
            'transactions': transactions,
            'goals': goals,
            'analytics': analytics,
        },
    )


@method_decorator(ensure_csrf_cookie, name='dispatch')
class DashboardLoginView(LoginView):
    authentication_form = AuthenticationForm
    template_name = 'dashboard/auth/login.html'
    redirect_authenticated_user = True


@ensure_csrf_cookie
def signup(request):
    if request.user.is_authenticated:
        return redirect('dashboard:index')

    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Conta criada com sucesso.')
            return redirect('dashboard:index')
    else:
        form = SignUpForm()

    return render(request, 'dashboard/auth/signup.html', {'form': form})


def logout_view(request):
    if request.method == 'POST':
        logout(request)
    return redirect('dashboard:login')


def csrf_failure(request, reason=''):
    return render(
        request,
        'dashboard/auth/csrf_failure.html',
        {'reason': reason},
        status=403,
    )
