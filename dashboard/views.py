from decimal import Decimal
from decimal import InvalidOperation
from datetime import datetime
from datetime import timedelta
import os

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.http import JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.cache import never_cache
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
from .forms import BankAccountForm
from .forms import BetFilterForm
from .forms import BetForm
from .forms import EntityForm
from .forms import EventOddsForm
from .forms import ImportTextForm
from .forms import MonthlyGoalForm
from .forms import BookmakerAliasForm
from .forms import OddsSearchForm
from .forms import PromotionExtractionForm
from .forms import PromotionForm
from .forms import PromotionPageForm
from .forms import RegulatedBookmakerForm
from .forms import RegulatedImportForm
from .forms import SignUpForm
from .forms import TransferForm
from .forms import UserPreferenceForm
from .models import BookmakerAlias
from .models import BookmakerEventLink
from .models import BankAccount
from .models import Bankroll
from .models import BankrollTransaction
from .models import Bet
from .models import Entity
from .models import FreeBet
from .models import MonthlyGoal
from .models import OddsSnapshot
from .models import Promotion
from .models import PromotionPage
from .models import RegulatedBookmaker
from .models import SureBetEntry
from .models import UserAccess
from .models import ensure_user_access
from .models import ensure_user_preference
from .odds_api import OddsApiClient
from .odds_api import OddsApiError
from .odds_api import OddsPapiClient
from .odds_api import BRAZIL_PRIORITY_BOOKMAKER_TERMS
from .odds_api import build_event_odds_board
from .odds_api import build_odds_comparison
from .odds_api import detect_surebets
from .odds_api import normalize_bookmaker_text
from .odds_crawler import DEFAULT_BOOKMAKERS as CRAWLER_DEFAULT_BOOKMAKERS
from .odds_crawler import capture_event_odds
from .odds_crawler import latest_event_odds
from .odds_crawler import normalize_bookmaker_list as normalize_crawler_bookmakers
from .promotion_scan import scan_user_promotion_pages
from .result_settlement import create_protection_balance_movements


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

DASHBOARD_BET_TYPE_CHOICES = [
    ('all', 'Todas'),
    ('simple', 'Apostas simples'),
    ('arbitrage', 'Arbitragem'),
    ('freebet_extraction', 'Extração de freebet'),
]

ODDS_CACHE_TIMEOUT = 60 * 15
EVENT_SEARCH_CACHE_TIMEOUT = 60 * 20

ODDSPAPI_SPORT_IDS = {
    'soccer_epl': 10,
    'soccer_brazil_campeonato': 10,
    'soccer_uefa_champs_league': 10,
    'soccer_spain_la_liga': 10,
    'soccer_italy_serie_a': 10,
    'soccer_germany_bundesliga': 10,
    'soccer_france_ligue_one': 10,
    'basketball_nba': 11,
    'americanfootball_nfl': 15,
}

ODDSPAPI_BRAZIL_BOOKMAKERS = [
    'sportingbet.bet.br',
    'stake.bet.br',
    'betnacional',
    'betano',
    'superbet',
    'estrelabet',
    'kto',
    'bet365',
    'betfair-spb',
    'bolsadeaposta-spb',
]

EVENT_SOURCE_THE_ODDS_API = 'the_odds_api'
EVENT_SOURCE_ODDSPAPI = 'oddspapi'
PROTECTION_STRATEGIES = {'Surebet', 'Proteção', 'Arbitragem', 'Extração de freebet'}


def redirect_to_history():
    return redirect(f'{reverse("dashboard:index")}#bets')


def is_protection_bet(bet):
    return bet.strategy in PROTECTION_STRATEGIES


def dashboard_bet_type(bet):
    if bet.strategy == 'Extração de freebet':
        return 'freebet_extraction'
    if is_protection_bet(bet):
        return 'arbitrage'
    return 'simple'


def protection_winner_net_result(bet, entries, winner):
    if bet.strategy == 'Extração de freebet':
        return sum(
            (entry.settlement_result_for(winner) for entry in entries),
            start=Decimal('0.00'),
        ).quantize(Decimal('0.01'))
    return winner.net_result


def apply_manual_protection_winner(bet, entries, winner, user):
    with transaction.atomic():
        entries.update(is_winner=False)
        winner.is_winner = True
        winner.save(update_fields=['is_winner'])
        bet.actual_net_result = protection_winner_net_result(bet, entries, winner)
        bet.status = Bet.Status.WON if bet.actual_net_result >= 0 else Bet.Status.LOST
        bet.exact_score = f'{winner.bookmaker} - {winner.label}'[:40]
        bet.save(update_fields=['actual_net_result', 'status', 'exact_score'])
        create_protection_balance_movements(bet, entries, winner)

        for entry in entries:
            if not entry.freebet_enabled or entry.freebet_amount <= 0:
                continue
            should_create_freebet = (
                entry.freebet_trigger == SureBetEntry.FreeBetTrigger.ANY
                or (
                    entry.freebet_trigger == SureBetEntry.FreeBetTrigger.WON
                    and entry.pk == winner.pk
                )
                or (
                    entry.freebet_trigger == SureBetEntry.FreeBetTrigger.LOST
                    and entry.pk != winner.pk
                )
            )
            if should_create_freebet:
                FreeBet.objects.get_or_create(
                    source_bet=bet,
                    bookmaker=entry.bookmaker,
                    amount=entry.freebet_amount,
                    defaults={'owner': user},
                )


def selected_winner_signature(bet, entry_id):
    winner = bet.surebet_entries.filter(pk=entry_id).first() if entry_id else None
    if winner is None:
        return None
    return winner.bookmaker, winner.label


def find_winner_by_signature(entries, signature):
    if signature is None:
        return None
    bookmaker, label = signature
    return entries.filter(bookmaker=bookmaker, label=label).first() or entries.filter(label=label).first()


def sales_page(request):
    user_access = ensure_user_access(request.user) if request.user.is_authenticated else None
    login_form = AuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST' and request.POST.get('form_type') == 'sales_login':
        if login_form.is_valid():
            login(request, login_form.get_user())
            return redirect('dashboard:index')
    elif request.method != 'POST':
        login_form = AuthenticationForm(request)

    return render(request, 'dashboard/sales.html', {'login_form': login_form, 'user_access': user_access})



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

    bet_type = request.GET.get('dashboard_bet_type') or 'all'
    valid_bet_types = {value for value, _label in DASHBOARD_BET_TYPE_CHOICES}
    if bet_type not in valid_bet_types:
        bet_type = 'all'

    return {
        'year': year,
        'month': month,
        'bet_type': bet_type,
        'bet_type_choices': DASHBOARD_BET_TYPE_CHOICES,
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
    user_access = ensure_user_access(request.user)
    user_preference = ensure_user_preference(request.user)
    entities = Entity.objects.filter(owner=request.user).prefetch_related('bankrolls')
    bank_accounts = BankAccount.objects.filter(owner=request.user)
    bankrolls = Bankroll.objects.filter(owner=request.user).select_related('entity').prefetch_related('bets', 'transactions')
    all_bets = user_bets(request.user).select_related('bankroll', 'bankroll__entity', 'entity')
    all_bet_list = list(all_bets)
    dashboard_filter = dashboard_period(request, all_bet_list)
    filtered_all_bet_list = [
        bet
        for bet in all_bet_list
        if dashboard_filter['bet_type'] == 'all'
        or dashboard_bet_type(bet) == dashboard_filter['bet_type']
    ]
    dashboard_bets = [
        bet
        for bet in filtered_all_bet_list
        if dashboard_filter['reference_date'] <= timezone.localtime(bet.created_at) < dashboard_filter['next_month']
    ]
    filter_form = forms.get('filter_form') or BetFilterForm(request.GET or None, user=request.user)
    bets = apply_bet_filters(all_bets, filter_form)

    settled_bets = [bet for bet in dashboard_bets if bet.status != Bet.Status.OPEN]
    total_stake = sum((bet.stake for bet in dashboard_bets), start=Decimal('0.00'))
    total_registered_stake = sum((bet.stake for bet in filtered_all_bet_list), start=Decimal('0.00'))
    net_profit = sum((bet.net_result for bet in dashboard_bets), start=Decimal('0.00'))
    won_bets = sum(1 for bet in dashboard_bets if bet.status == Bet.Status.WON)
    open_exposure = sum(
        (bet.stake for bet in dashboard_bets if bet.status == Bet.Status.OPEN),
        start=Decimal('0.00'),
    )
    open_bet_count = sum(1 for bet in dashboard_bets if bet.status == Bet.Status.OPEN)
    available_freebets = FreeBet.objects.filter(
        Q(owner=request.user)
        | Q(source_bet__bankroll__owner=request.user)
        | Q(source_bet__entity__owner=request.user),
        is_used=False,
    ).distinct()
    freebet_cycles_base = FreeBet.objects.filter(
        source_bet__isnull=False,
    ).filter(
        Q(source_bet__bankroll__owner=request.user)
        | Q(source_bet__entity__owner=request.user)
        | Q(owner=request.user)
    ).select_related('source_bet', 'extraction_bet')
    pending_freebet_cycles = freebet_cycles_base.filter(
        is_used=False,
        extraction_bet__isnull=True,
    )[:4]
    freebet_extraction_history = freebet_cycles_base.filter(
        Q(is_used=True) | Q(extraction_bet__isnull=False)
    )[:12]
    available_freebet_total = available_freebets.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
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
    total_open_exposure = sum(
        (bankroll.open_exposure for bankroll in bankrolls),
        start=Decimal('0.00'),
    )
    roi = (net_profit / total_stake * 100) if total_stake else Decimal('0.00')
    win_rate = (won_bets / len(settled_bets) * 100) if settled_bets else 0

    market_stats = []
    for market in sorted({bet.market for bet in filtered_all_bet_list}):
        market_bets = [bet for bet in filtered_all_bet_list if bet.market == market]
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
            and (
                dashboard_filter['bet_type'] == 'all'
                or dashboard_bet_type(bet) == dashboard_filter['bet_type']
            )
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
    ).select_related('bankroll', 'bank_account')[:8]
    primary_bank_account = bank_accounts.filter(name__icontains='principal').first() or bank_accounts.first()
    bank_account_summaries = []
    for bank_account in bank_accounts:
        bank_account_summaries.append(
            {
                'account': bank_account,
                'balance': bank_account.current_balance,
                'is_primary': primary_bank_account and bank_account.pk == primary_bank_account.pk,
            }
        )
    regulated_bookmakers = RegulatedBookmaker.objects.filter(owner=request.user).prefetch_related('aliases', 'promotion_pages')
    affiliate_terms = [
        'afiliado',
        'afiliados',
        'afiliação',
        'afiliacao',
        'affiliate',
        'indique e ganhe',
        'convide e ganhe',
        'programa de indicação',
        'programa de indicacao',
        'referral',
    ]
    affiliate_filter = Q()
    for term in affiliate_terms:
        affiliate_filter |= Q(title__icontains=term)
        affiliate_filter |= Q(public_text__icontains=term)
        affiliate_filter |= Q(source_url__icontains=term)
    promotions = (
        Promotion.objects.filter(bookmaker__owner=request.user, is_active=True)
        .exclude(affiliate_filter)
        .select_related('bookmaker', 'page')[:20]
    )
    promotion_pages = PromotionPage.objects.filter(bookmaker__owner=request.user).select_related('bookmaker')[:20]
    promotion_aliases = BookmakerAlias.objects.filter(bookmaker__owner=request.user).select_related('bookmaker')[:20]
    analytics = build_analytics(
        dashboard_bets,
        balance_before_period,
        dashboard_filter['reference_date'].date(),
    )

    return {
        'bankroll_form': forms.get('bankroll_form') or BankrollForm(user=request.user),
        'bank_account_form': forms.get('bank_account_form') or BankAccountForm(),
        'entity_form': forms.get('entity_form') or EntityForm(user=request.user),
        'form': forms.get('bet_form') or BetForm(user=request.user),
        'transaction_form': forms.get('transaction_form') or BankrollTransactionForm(user=request.user),
        'transfer_form': forms.get('transfer_form') or TransferForm(user=request.user),
        'preference_form': forms.get('preference_form') or UserPreferenceForm(instance=user_preference),
        'filter_form': filter_form,
        'import_form': forms.get('import_form') or ImportTextForm(),
        'event_odds_form': forms.get('event_odds_form') or EventOddsForm(prefix='event_odds'),
        'odds_form': forms.get('odds_form') or OddsSearchForm(),
        'odds_opportunities': forms.get('odds_opportunities') or [],
        'odds_comparisons': forms.get('odds_comparisons') or [],
        'odds_searched': forms.get('odds_searched') or False,
        'regulated_form': forms.get('regulated_form') or RegulatedBookmakerForm(),
        'regulated_import_form': forms.get('regulated_import_form') or RegulatedImportForm(),
        'alias_form': forms.get('alias_form') or BookmakerAliasForm(user=request.user),
        'promotion_page_form': forms.get('promotion_page_form') or PromotionPageForm(user=request.user),
        'promotion_form': forms.get('promotion_form') or PromotionForm(user=request.user),
        'promotion_extraction_form': forms.get('promotion_extraction_form') or PromotionExtractionForm(user=request.user),
        'promotion_extraction_result': forms.get('promotion_extraction_result'),
        'regulated_bookmakers': regulated_bookmakers,
        'promotions': promotions,
        'promotion_pages': promotion_pages,
        'promotion_aliases': promotion_aliases,
        'goal_form': forms.get('goal_form') or MonthlyGoalForm(user=request.user),
        'surebet_errors': forms.get('surebet_errors') or [],
        'surebet_data': forms.get('surebet_data') or {},
        'surebet_rows': build_surebet_rows(forms.get('surebet_data')),
        'freebet_extract_errors': forms.get('freebet_extract_errors') or [],
        'freebet_extract_data': forms.get('freebet_extract_data') or {},
        'freebet_extract_rows': build_freebet_extract_rows(forms.get('freebet_extract_data')),
        'freebet_manual_errors': forms.get('freebet_manual_errors') or [],
        'freebet_manual_data': forms.get('freebet_manual_data') or {},
        'available_freebet_list': available_freebets.select_related(
            'source_bet',
            'source_bet__entity',
            'source_bet__bankroll',
        ),
        'pending_freebet_cycles': pending_freebet_cycles,
        'freebet_extraction_history': freebet_extraction_history,
        'bankrolls': bankrolls,
        'bank_accounts': bank_accounts,
        'primary_bank_account': primary_bank_account,
        'bank_account_summaries': bank_account_summaries,
        'entities': entities,
        'bets': bets[:30],
        'latest_transactions': latest_transactions,
        'monthly_goals': MonthlyGoal.objects.filter(entity__owner=request.user).select_related('entity')[:12],
        'dashboard_filter': dashboard_filter,
        'user_access': user_access,
        'user_preference': user_preference,
        'currency_code': user_preference.currency,
        'currency_symbol': user_preference.currency_symbol,
        'currency_locale': user_preference.currency_locale,
        'metrics': {
            'total_stake': total_stake,
            'total_registered_stake': total_registered_stake,
            'net_profit': net_profit,
            'roi': roi,
            'win_rate': win_rate,
            'open_exposure': open_exposure,
            'open_bet_count': open_bet_count,
            'bet_count': len(filtered_all_bet_list),
            'total_initial_balance': total_initial_balance,
        'total_current_balance': total_current_balance,
        'total_available_balance': total_available_balance,
        'total_open_exposure': total_open_exposure,
            'available_freebets': available_freebet_total,
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


def prefixed_indices_from_post(post_data, prefix):
    indices = set()
    field_prefix = f'{prefix}_'
    for key in post_data.keys():
        if not key.startswith(field_prefix):
            continue
        suffix = key.rsplit('_', 1)[-1]
        if suffix.isdigit():
            indices.add(int(suffix))
    entry_count = decimal_from_post(post_data, f'{prefix}_entry_count')
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
                'bankroll_id': (post_data.get(f'surebet_bankroll_{index}') if post_data else '') or '',
                'outcome': (post_data.get(f'surebet_outcome_{index}') if post_data else '') or '',
                'mode': (post_data.get(f'surebet_mode_{index}') if post_data else '') or 'back',
                'odd': (post_data.get(f'surebet_odd_{index}') if post_data else '') or '',
                'stake': (post_data.get(f'surebet_stake_{index}') if post_data else '') or '',
                'net_result': (post_data.get(f'surebet_net_{index}') if post_data else '') or '',
                'commission': (post_data.get(f'surebet_commission_{index}') if post_data else '') or '',
                'cashback': (post_data.get(f'surebet_cashback_{index}') if post_data else '') or '',
                'boost': (post_data.get(f'surebet_boost_{index}') if post_data else '') or '',
                'freebet_enabled': (post_data.get(f'surebet_freebet_enabled_{index}') if post_data else '') or '',
                'freebet_amount': (post_data.get(f'surebet_freebet_amount_{index}') if post_data else '') or '',
                'freebet_trigger': (post_data.get(f'surebet_freebet_trigger_{index}') if post_data else '') or 'lost',
                'notes': (post_data.get(f'surebet_notes_{index}') if post_data else '') or '',
                'optional': index > 2,
                'readonly': index > 1,
            }
        )
    return rows


def build_freebet_extract_rows(post_data=None):
    indices = prefixed_indices_from_post(post_data, 'freebet') if post_data else [1, 2, 3]
    rows = []
    for index in indices:
        rows.append(
            {
                'index': index,
                'bookmaker': (post_data.get(f'freebet_bookmaker_{index}') if post_data else '') or '',
                'bankroll_id': (post_data.get(f'freebet_bankroll_{index}') if post_data else '') or '',
                'outcome': (post_data.get(f'freebet_outcome_{index}') if post_data else '') or '',
                'mode': (post_data.get(f'freebet_mode_{index}') if post_data else '') or 'back',
                'odd': (post_data.get(f'freebet_odd_{index}') if post_data else '') or '',
                'stake': (post_data.get(f'freebet_stake_{index}') if post_data else '') or '',
                'commission': (post_data.get(f'freebet_commission_{index}') if post_data else '') or '',
                'cashback': (post_data.get(f'freebet_cashback_{index}') if post_data else '') or '',
                'boost': (post_data.get(f'freebet_boost_{index}') if post_data else '') or '',
                'freebet_enabled': (post_data.get(f'freebet_freebet_enabled_{index}') if post_data else '') or '',
                'freebet_amount': (post_data.get(f'freebet_freebet_amount_{index}') if post_data else '') or '',
                'notes': (post_data.get(f'freebet_notes_{index}') if post_data else '') or '',
                'optional': index > 2,
                'readonly': index > 1,
                'is_source': index == 1,
            }
        )
    return rows


def decimal_to_input(value):
    if value is None:
        return ''
    return f'{value:.2f}'


def datetime_to_input(value):
    if not value:
        return ''
    return timezone.localtime(value).strftime('%Y-%m-%d')


def surebet_data_from_bet(bet):
    return {
        'surebet_entity': str(bet.entity_id or ''),
        'surebet_sport': bet.sport,
        'surebet_competition': bet.competition,
        'surebet_event_date': datetime_to_input(bet.event_date),
        'surebet_game': bet.game,
        'surebet_external_event_id': bet.external_event_id,
        'surebet_external_sport_key': bet.external_sport_key,
        'surebet_home_team': bet.home_team,
        'surebet_away_team': bet.away_team,
        'surebet_general_notes': bet.notes,
    }


def freebet_data_from_bet(bet, source_freebet=None):
    return {
        'freebet_source': str(source_freebet.pk if source_freebet else ''),
        'freebet_sport': bet.sport,
        'freebet_competition': bet.competition,
        'freebet_event_date': datetime_to_input(bet.event_date),
        'freebet_game': bet.game,
        'freebet_external_event_id': bet.external_event_id,
        'freebet_external_sport_key': bet.external_sport_key,
        'freebet_home_team': bet.home_team,
        'freebet_away_team': bet.away_team,
        'freebet_general_notes': bet.notes,
    }


def rows_from_surebet_entries(bet, prefix):
    entries = list(bet.surebet_entries.select_related('bankroll').order_by('id'))
    rows = []
    for index, entry in enumerate(entries, start=1):
        rows.append(
            {
                'index': index,
                'bookmaker': entry.bookmaker,
                'bankroll_id': str(entry.bankroll_id or ''),
                'outcome': entry.label,
                'mode': entry.mode,
                'odd': decimal_to_input(entry.odds),
                'stake': decimal_to_input(entry.stake),
                'net_result': decimal_to_input(entry.net_result),
                'commission': decimal_to_input(entry.commission),
                'cashback': decimal_to_input(entry.cashback),
                'boost': decimal_to_input(entry.boost),
                'freebet_enabled': '1' if entry.freebet_enabled else '',
                'freebet_amount': decimal_to_input(entry.freebet_amount) if entry.freebet_amount else '',
                'freebet_trigger': entry.freebet_trigger,
                'notes': entry.notes,
                'optional': index > 2,
                'readonly': index > 1,
                'is_source': entry.is_freebet_source,
            }
        )
    while len(rows) < 2:
        index = len(rows) + 1
        rows.append(
            {
                'index': index,
                'bookmaker': '',
                'bankroll_id': '',
                'outcome': '',
                'mode': 'back',
                'odd': '',
                'stake': '',
                'net_result': '',
                'commission': '',
                'cashback': '',
                'boost': '',
                'freebet_enabled': '',
                'freebet_amount': '',
                'freebet_trigger': 'lost',
                'notes': '',
                'optional': index > 2,
                'readonly': index > 1,
                'is_source': prefix == 'freebet' and index == 1,
            }
        )
    if prefix == 'freebet' and rows:
        rows[0]['is_source'] = True
        rows[0]['readonly'] = False
    return rows


def calculate_protection_results(outcomes):
    total_stake = sum(
        (
            outcome['liability'] if outcome['mode'] == 'lay' else outcome['stake']
            for outcome in outcomes
        ),
        start=Decimal('0.00'),
    )
    outcome_results = [
        {
            **outcome,
            'return': (outcome['stake'] * outcome['payout_multiplier']).quantize(Decimal('0.01')),
        }
        for outcome in outcomes
    ]
    for outcome in outcome_results:
        losing_cashback = sum(
            (
                other['stake'] * (other['cashback'] / Decimal('100'))
                for other in outcome_results
                if other is not outcome and other['mode'] == 'back'
            ),
            start=Decimal('0.00'),
        )
        scenario_net = outcome['return'] - total_stake
        outcome['cashback_return'] = losing_cashback.quantize(Decimal('0.01'))
        calculated_net = (scenario_net + outcome['cashback_return']).quantize(Decimal('0.01'))
        outcome['net'] = (
            outcome['manual_net_result']
            if outcome['manual_net_result'] is not None else calculated_net
        )
        outcome['effective_odd_display'] = outcome['effective_odd'].quantize(Decimal('0.01'))
    return total_stake, outcome_results


def calculate_freebet_results(outcomes):
    cash_exposure = sum(
        (
            Decimal('0.00')
            if outcome['is_freebet_source']
            else outcome['liability'] if outcome['mode'] == 'lay' else outcome['stake']
        )
        for outcome in outcomes
    )
    outcome_results = [
        {
            **outcome,
            'return': (outcome['stake'] * outcome['payout_multiplier']).quantize(Decimal('0.01')),
        }
        for outcome in outcomes
    ]
    for outcome in outcome_results:
        losing_cashback = sum(
            (
                other['stake'] * (other['cashback'] / Decimal('100'))
                for other in outcome_results
                if other is not outcome
                and not other['is_freebet_source']
                and other['mode'] == 'back'
            ),
            start=Decimal('0.00'),
        )
        scenario_net = Decimal('0.00')
        for entry in outcome_results:
            if entry is outcome:
                if entry['is_freebet_source']:
                    scenario_net += entry['return']
                elif entry['mode'] == 'lay':
                    scenario_net += entry['return'] - entry['liability']
                else:
                    scenario_net += entry['return'] - entry['stake']
            elif outcome['is_freebet_source'] and entry['mode'] == 'lay':
                scenario_net -= entry['liability']
            elif entry['is_freebet_source']:
                scenario_net += Decimal('0.00')
            elif entry['mode'] == 'lay':
                scenario_net -= entry['liability']
            else:
                scenario_net -= entry['stake']
        outcome['cashback_return'] = losing_cashback.quantize(Decimal('0.01'))
        outcome['net'] = (scenario_net + outcome['cashback_return']).quantize(Decimal('0.01'))
        outcome['effective_odd_display'] = outcome['effective_odd'].quantize(Decimal('0.01'))
    return cash_exposure, outcome_results


def build_surebet_payload(post_data):
    outcomes = []
    for index in surebet_indices_from_post(post_data):
        bookmaker = (post_data.get(f'surebet_bookmaker_{index}') or '').strip()
        bankroll_id = (post_data.get(f'surebet_bankroll_{index}') or '').strip()
        mode = (post_data.get(f'surebet_mode_{index}') or 'back').strip().lower()
        if mode not in {'back', 'lay'}:
            mode = 'back'
        label = (post_data.get(f'surebet_outcome_{index}') or '').strip()
        odd = decimal_from_post(post_data, f'surebet_odd_{index}')
        stake = decimal_from_post(post_data, f'surebet_stake_{index}')
        manual_net_result = decimal_from_post(post_data, f'surebet_net_{index}', default='')
        commission = decimal_from_post(post_data, f'surebet_commission_{index}')
        cashback = decimal_from_post(post_data, f'surebet_cashback_{index}')
        boost = decimal_from_post(post_data, f'surebet_boost_{index}')
        freebet_enabled = post_data.get(f'surebet_freebet_enabled_{index}') == '1'
        freebet_amount = decimal_from_post(post_data, f'surebet_freebet_amount_{index}')
        freebet_trigger = (post_data.get(f'surebet_freebet_trigger_{index}') or 'lost').strip().lower()
        if freebet_trigger not in {'won', 'lost', 'any'}:
            freebet_trigger = 'lost'
        entry_notes = (post_data.get(f'surebet_notes_{index}') or '').strip()
        if (
            not bookmaker
            and not bankroll_id
            and not label
            and (not odd or odd == 0)
            and (not stake or stake == 0)
            and manual_net_result is None
            and (not commission or commission == 0)
            and (not cashback or cashback == 0)
            and (not boost or boost == 0)
            and not freebet_enabled
            and (not freebet_amount or freebet_amount == 0)
            and not entry_notes
        ):
            continue
        commission = commission or Decimal('0.00')
        cashback = cashback or Decimal('0.00')
        boost = boost or Decimal('0.00')
        freebet_amount = freebet_amount or Decimal('0.00')
        effective_odd = odd * (Decimal('1.00') + boost / Decimal('100')) if odd else None
        payout_multiplier = None
        if effective_odd and effective_odd > 1:
            if mode == 'lay':
                payout_multiplier = effective_odd - commission / Decimal('100')
            else:
                payout_multiplier = Decimal('1.00') + (
                    (effective_odd - Decimal('1.00'))
                    * (Decimal('1.00') - commission / Decimal('100'))
                )
        liability = Decimal('0.00')
        if mode == 'lay' and effective_odd and stake:
            liability = (stake * (effective_odd - Decimal('1.00'))).quantize(Decimal('0.01'))
        outcomes.append(
            {
                'bookmaker': bookmaker,
                'bankroll_id': bankroll_id,
                'bankroll': None,
                'label': label or f'Entrada {index}',
                'mode': mode,
                'odd': odd,
                'stake': stake,
                'manual_net_result': (
                    manual_net_result.quantize(Decimal('0.01'))
                    if manual_net_result is not None else None
                ),
                'liability': liability,
                'commission': commission,
                'cashback': cashback,
                'boost': boost,
                'freebet_enabled': freebet_enabled,
                'freebet_amount': freebet_amount,
                'freebet_trigger': freebet_trigger,
                'notes': entry_notes,
                'effective_odd': effective_odd,
                'payout_multiplier': payout_multiplier,
            }
        )
    return outcomes


def build_freebet_extract_payload(post_data, source_freebet=None):
    outcomes = []
    target_return = None
    source_amount = source_freebet.amount if source_freebet else Decimal('0.00')
    for index in prefixed_indices_from_post(post_data, 'freebet'):
        bookmaker = (post_data.get(f'freebet_bookmaker_{index}') or '').strip()
        bankroll_id = (post_data.get(f'freebet_bankroll_{index}') or '').strip()
        if index == 1 and source_freebet and not bookmaker:
            bookmaker = source_freebet.bookmaker
        mode = (post_data.get(f'freebet_mode_{index}') or 'back').strip().lower()
        if mode not in {'back', 'lay'}:
            mode = 'back'
        if index == 1:
            mode = 'back'
        label = (post_data.get(f'freebet_outcome_{index}') or '').strip()
        odd = decimal_from_post(post_data, f'freebet_odd_{index}')
        stake = decimal_from_post(post_data, f'freebet_stake_{index}')
        commission = decimal_from_post(post_data, f'freebet_commission_{index}')
        cashback = decimal_from_post(post_data, f'freebet_cashback_{index}')
        boost = decimal_from_post(post_data, f'freebet_boost_{index}')
        freebet_enabled = post_data.get(f'freebet_freebet_enabled_{index}') == '1'
        freebet_amount = decimal_from_post(post_data, f'freebet_freebet_amount_{index}')
        freebet_trigger = 'lost'
        entry_notes = (post_data.get(f'freebet_notes_{index}') or '').strip()
        if (
            index != 1
            and not bookmaker
            and not bankroll_id
            and not label
            and (not odd or odd == 0)
            and (not stake or stake == 0)
            and (not commission or commission == 0)
            and (not cashback or cashback == 0)
            and (not boost or boost == 0)
            and not freebet_enabled
            and (not freebet_amount or freebet_amount == 0)
            and not entry_notes
        ):
            continue
        commission = commission or Decimal('0.00')
        cashback = cashback or Decimal('0.00')
        boost = boost or Decimal('0.00')
        freebet_amount = freebet_amount or Decimal('0.00')
        if index == 1 and source_amount > 0 and not stake:
            stake = source_amount
        effective_odd = odd * (Decimal('1.00') + boost / Decimal('100')) if odd else None
        payout_multiplier = None
        if effective_odd and effective_odd > 1:
            if index == 1:
                payout_multiplier = (effective_odd - Decimal('1.00')) * (
                    Decimal('1.00') - commission / Decimal('100')
                )
            elif mode == 'lay':
                payout_multiplier = effective_odd
            else:
                payout_multiplier = Decimal('1.00') + (
                    (effective_odd - Decimal('1.00'))
                    * (Decimal('1.00') - commission / Decimal('100'))
                )
        if index == 1 and stake and stake > 0 and payout_multiplier and payout_multiplier > 0:
            target_return = (stake * payout_multiplier).quantize(Decimal('0.01'))
        elif (
            target_return
            and payout_multiplier
            and payout_multiplier > 0
            and (not stake or stake == 0)
        ):
            stake = (target_return / payout_multiplier).quantize(Decimal('0.01'))
        liability = Decimal('0.00')
        if mode == 'lay' and effective_odd and stake:
            liability = (stake * (effective_odd - Decimal('1.00'))).quantize(Decimal('0.01'))
        outcomes.append(
            {
                'index': index,
                'bookmaker': bookmaker,
                'bankroll_id': bankroll_id,
                'bankroll': None,
                'label': label or ('Freebet' if index == 1 else f'Arbitragem {index}'),
                'mode': mode,
                'odd': odd,
                'stake': stake,
                'liability': liability,
                'commission': commission,
                'cashback': cashback,
                'boost': boost,
                'freebet_enabled': freebet_enabled,
                'freebet_amount': freebet_amount,
                'freebet_trigger': freebet_trigger,
                'notes': entry_notes,
                'effective_odd': effective_odd,
                'payout_multiplier': payout_multiplier,
                'is_freebet_source': index == 1,
            }
        )
    return outcomes


def format_money(value):
    return f'R$ {value.quantize(Decimal("0.01"))}'


def event_date_from_post(post_data, field_name):
    raw_value = (post_data.get(field_name) or '').strip()
    if not raw_value:
        return None
    parsed_date = parse_date(raw_value)
    if parsed_date is not None:
        return timezone.make_aware(
            datetime.combine(parsed_date, datetime.min.time()),
            timezone.get_current_timezone(),
        )
    parsed = parse_datetime(raw_value)
    if parsed is None:
        parsed = parse_datetime(f'{raw_value}:00')
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def freebet_trigger_label(trigger):
    labels = {
        'won': 'se ganhar',
        'lost': 'se perder',
        'any': 'em ambos os casos',
    }
    return labels.get(trigger, labels['lost'])


def bankroll_display_name(bankroll):
    return bankroll.display_name


def bind_outcome_bankrolls(outcomes, user, errors, entity=None):
    bankroll_ids = [outcome['bankroll_id'] for outcome in outcomes if outcome.get('bankroll_id')]
    bankrolls = {
        str(bankroll.pk): bankroll
        for bankroll in Bankroll.objects.filter(pk__in=bankroll_ids, owner=user).select_related('entity')
    }
    for outcome in outcomes:
        bankroll_id = outcome.get('bankroll_id')
        if not bankroll_id:
            errors.append(f'Selecione a banca/casa de aposta de {outcome["label"]}.')
            continue
        bankroll = bankrolls.get(str(bankroll_id))
        if bankroll is None:
            errors.append(f'A banca/casa de {outcome["label"]} não é válida para este usuário.')
            continue
        if entity is not None and bankroll.entity_id and bankroll.entity_id != entity.id:
            errors.append(
                f'A banca/casa de {outcome["label"]} pertence a outra entidade.'
            )
            continue
        outcome['bankroll'] = bankroll
        outcome['bookmaker'] = bankroll_display_name(bankroll)


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


def regulated_bookmaker_terms_for_user(user):
    terms = [
        normalize_bookmaker_text(term)
        for term in BRAZIL_PRIORITY_BOOKMAKER_TERMS
        if normalize_bookmaker_text(term)
    ]
    aliases = BookmakerAlias.objects.filter(
        bookmaker__owner=user,
        provider='the_odds_api',
    ).select_related('bookmaker')
    for alias in aliases:
        bookmaker_terms = {
            normalize_bookmaker_text(alias.bookmaker.brand),
            normalize_bookmaker_text(alias.bookmaker.domain.split('.')[0] if alias.bookmaker.domain else ''),
        }
        if not bookmaker_terms.intersection(terms):
            continue
        candidates = [
            alias.provider_key,
            alias.alias,
            alias.bookmaker.brand,
            alias.bookmaker.domain.split('.')[0] if alias.bookmaker.domain else '',
        ]
        for candidate in candidates:
            term = normalize_bookmaker_text(candidate)
            if term and term not in terms:
                terms.append(term)
    return terms


def odds_bookmakers_for_request(user, cleaned_data):
    manual_bookmakers = (cleaned_data.get('bookmakers') or '').strip()
    if manual_bookmakers:
        return manual_bookmakers, False, []
    if cleaned_data.get('brazil_regulated_only'):
        terms = regulated_bookmaker_terms_for_user(user)
        if terms:
            return '', True, terms
    return '', False, []


def import_regulated_bookmakers_from_text(user, raw_text):
    imported = 0
    updated = 0
    errors = []
    valid_statuses = {choice[0] for choice in RegulatedBookmaker.Status.choices}
    for line_number, raw_line in enumerate(raw_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split(';')]
        if len(parts) < 4:
            errors.append(f'Linha {line_number}: use empresa;cnpj;marca;dominio;status.')
            continue
        company_name, cnpj, brand, domain = parts[:4]
        status = parts[4] if len(parts) > 4 and parts[4] else RegulatedBookmaker.Status.AUTHORIZED
        if status not in valid_statuses:
            status = RegulatedBookmaker.Status.AUTHORIZED
        domain = domain.lower().replace('https://', '').replace('http://', '').strip('/')
        if not domain:
            errors.append(f'Linha {line_number}: domínio obrigatório.')
            continue
        _, created = RegulatedBookmaker.objects.update_or_create(
            owner=user,
            domain=domain,
            defaults={
                'company_name': company_name,
                'cnpj': cnpj,
                'brand': brand,
                'status': status,
                'source': 'SPA/MF',
                'last_checked_at': timezone.now(),
                'judicial_alert': status == RegulatedBookmaker.Status.JUDICIAL_ALERT,
            },
        )
        if created:
            imported += 1
        else:
            updated += 1
    return imported, updated, errors


def calculate_promotion_extraction(promotion, freebet_odd, protection_odd, protection_commission=Decimal('0.00')):
    amount = promotion.freebet_amount
    freebet_return = (amount * (freebet_odd - Decimal('1.00'))).quantize(Decimal('0.01'))
    protection_multiplier = Decimal('1.00') + (
        (protection_odd - Decimal('1.00'))
        * (Decimal('1.00') - (protection_commission or Decimal('0.00')) / Decimal('100'))
    )
    protection_stake = (freebet_return / protection_multiplier).quantize(Decimal('0.01'))
    if promotion.trigger == Promotion.Trigger.LOST:
        if_freebet_loses = (protection_stake * protection_multiplier - protection_stake).quantize(Decimal('0.01'))
        if_freebet_wins = (freebet_return - protection_stake).quantize(Decimal('0.01'))
    elif promotion.trigger == Promotion.Trigger.WON:
        if_freebet_wins = (freebet_return - protection_stake).quantize(Decimal('0.01'))
        if_freebet_loses = (protection_stake * protection_multiplier - protection_stake).quantize(Decimal('0.01'))
    else:
        if_freebet_wins = (freebet_return - protection_stake).quantize(Decimal('0.01'))
        if_freebet_loses = (protection_stake * protection_multiplier - protection_stake).quantize(Decimal('0.01'))
    worst = min(if_freebet_wins, if_freebet_loses)
    conversion = (worst / amount * Decimal('100')).quantize(Decimal('0.01')) if amount else Decimal('0.00')
    return {
        'promotion': promotion,
        'freebet_return': freebet_return,
        'protection_stake': protection_stake,
        'if_freebet_wins': if_freebet_wins,
        'if_freebet_loses': if_freebet_loses,
        'worst': worst,
        'conversion': conversion,
    }


def guess_event_sports(sport_text, competition_text):
    text = f'{sport_text or ""} {competition_text or ""}'.lower()
    choices = dict(OddsSearchForm.SPORT_CHOICES)
    if sport_text in choices:
        return [sport_text]
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


def get_oddspapi_api_key():
    return os.environ.get('ODDSPAPI_API_KEY') or os.environ.get('ODDS_PAPI_API_KEY')


def oddspapi_sport_id(sport_key):
    return ODDSPAPI_SPORT_IDS.get(sport_key or '', 10)


def oddspapi_fixture_window():
    now = timezone.now()
    return (
        now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        (now + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%SZ'),
    )


def normalize_oddspapi_event(event, sport_key=''):
    home_team = event.get('participant1Name') or event.get('participant1ShortName') or ''
    away_team = event.get('participant2Name') or event.get('participant2ShortName') or ''
    starts_at = parse_datetime(event.get('startTime') or '') if event.get('startTime') else None
    local_starts_at = timezone.localtime(starts_at) if starts_at else None
    sport_name = event.get('sportName') or ''
    fixture_id = event.get('fixtureId')
    return {
        'id': f'{EVENT_SOURCE_ODDSPAPI}:{fixture_id}' if fixture_id else '',
        'game': f'{home_team} x {away_team}'.strip(' x'),
        'home_team': home_team,
        'away_team': away_team,
        'sport_key': sport_key,
        'competition': event.get('tournamentName') or event.get('tournamentSlug') or '',
        'sport': 'Futebol' if sport_name.lower() == 'soccer' else sport_name,
        'event_date': local_starts_at.strftime('%Y-%m-%dT%H:%M') if local_starts_at else '',
        'display_date': local_starts_at.strftime('%d/%m/%Y %H:%M') if local_starts_at else '',
    }


def normalize_event(event):
    home_team = event.get('home_team') or ''
    away_team = event.get('away_team') or ''
    commence_time = event.get('commence_time') or ''
    starts_at = parse_datetime(commence_time) if commence_time else None
    local_starts_at = timezone.localtime(starts_at) if starts_at else None
    return {
        'id': f'{EVENT_SOURCE_THE_ODDS_API}:{event.get("id")}' if event.get('id') else '',
        'game': f'{home_team} x {away_team}'.strip(' x'),
        'home_team': home_team,
        'away_team': away_team,
        'sport_key': event.get('sport_key') or '',
        'competition': event.get('sport_title') or '',
        'sport': 'Futebol' if (event.get('sport_key') or '').startswith('soccer') else event.get('sport_title') or '',
        'event_date': local_starts_at.strftime('%Y-%m-%dT%H:%M') if local_starts_at else '',
        'display_date': local_starts_at.strftime('%d/%m/%Y %H:%M') if local_starts_at else '',
    }


def crawler_bookmakers_for_request(cleaned_data):
    manual_bookmakers = (cleaned_data.get('bookmakers') or '').strip()
    if manual_bookmakers:
        return normalize_crawler_bookmakers(manual_bookmakers)
    if cleaned_data.get('brazil_regulated_only'):
        return CRAWLER_DEFAULT_BOOKMAKERS
    return CRAWLER_DEFAULT_BOOKMAKERS


def build_crawler_event_payload(external_event_id, home_team, away_team, start_time, bookmakers):
    return {
        'external_event_id': external_event_id,
        'home_team': home_team,
        'away_team': away_team,
        'start_time': start_time,
        'bookmakers': bookmakers,
    }


def build_crawler_event_odds_board(event, snapshots, used_cache=False):
    outcome_names = [
        event['home_team'] or 'Mandante',
        'Empate',
        event['away_team'] or 'Visitante',
    ]
    bookmaker_rows = {}
    for snapshot in snapshots:
        row = bookmaker_rows.setdefault(
            snapshot.bookmaker,
            {
                'key': snapshot.bookmaker,
                'title': snapshot.bookmaker,
                'last_update': snapshot.captured_at.isoformat(),
                'outcomes': {},
            },
        )
        row['outcomes'][snapshot.selection] = float(snapshot.odd)

    return {
        'event': f'{event["home_team"]} x {event["away_team"]}'.strip(' x'),
        'sport': 'Crawler de casas brasileiras',
        'commence_time': event.get('start_time') or '',
        'outcome_names': outcome_names,
        'bookmakers': list(bookmaker_rows.values()),
        'filter_note': (
            ''
            if bookmaker_rows
            else 'Nenhuma odd capturada ainda. Os adapters das casas precisam encontrar o evento público primeiro.'
        ),
        'provider': 'crawler',
        'used_cache': used_cache,
    }


def build_standard_events_from_snapshots(snapshots):
    events = []
    snapshots_by_event = {}
    for snapshot in snapshots:
        snapshots_by_event.setdefault(snapshot.external_event_id, []).append(snapshot)

    for external_event_id, event_snapshots in snapshots_by_event.items():
        link = (
            BookmakerEventLink.objects.filter(external_event_id=external_event_id)
            .order_by('-last_checked_at')
            .first()
        )
        home_team = link.home_team if link else ''
        away_team = link.away_team if link else ''
        bookmakers = {}
        for snapshot in event_snapshots:
            bookmaker = bookmakers.setdefault(
                snapshot.bookmaker,
                {
                    'key': snapshot.bookmaker,
                    'title': snapshot.bookmaker,
                    'last_update': snapshot.captured_at.isoformat(),
                    'markets': [
                        {
                            'key': 'h2h',
                            'outcomes': [],
                        }
                    ],
                },
            )
            bookmaker['markets'][0]['outcomes'].append(
                {
                    'name': snapshot.selection,
                    'price': float(snapshot.odd),
                }
            )
        events.append(
            {
                'id': external_event_id,
                'home_team': home_team,
                'away_team': away_team,
                'sport_title': 'Crawler',
                'commence_time': '',
                'bookmakers': list(bookmakers.values()),
            }
        )
    return events


def oddspapi_bookmaker_terms_for_request(cleaned_data):
    manual_bookmakers = (cleaned_data.get('bookmakers') or '').strip()
    if manual_bookmakers:
        return manual_bookmakers, []
    if cleaned_data.get('brazil_regulated_only'):
        return ','.join(ODDSPAPI_BRAZIL_BOOKMAKERS), [
            normalize_bookmaker_text(bookmaker)
            for bookmaker in ODDSPAPI_BRAZIL_BOOKMAKERS
        ]
    return '', []


def parse_oddspapi_restricted_bookmakers(error):
    message = str(error)
    marker = 'Restricted bookmakers:'
    if marker not in message:
        return []
    restricted_text = message.split(marker, 1)[1].split('.', 1)[0]
    return [
        bookmaker.strip()
        for bookmaker in restricted_text.split(',')
        if bookmaker.strip()
    ]


def without_restricted_bookmakers(bookmakers, restricted_bookmakers):
    restricted_terms = {normalize_bookmaker_text(bookmaker) for bookmaker in restricted_bookmakers}
    allowed = [
        bookmaker.strip()
        for bookmaker in (bookmakers or '').split(',')
        if bookmaker.strip() and normalize_bookmaker_text(bookmaker) not in restricted_terms
    ]
    return ','.join(allowed)


def oddspapi_outcome_label(raw_value, event):
    normalized = normalize_bookmaker_text(raw_value)
    home_team = event.get('participant1Name') or event.get('participant1ShortName') or 'Casa'
    away_team = event.get('participant2Name') or event.get('participant2ShortName') or 'Visitante'
    if normalized in {'home', 'team1', 'participant1', '1'} or normalized.endswith('_home'):
        return home_team
    if normalized in {'away', 'team2', 'participant2', '2'} or normalized.endswith('_away'):
        return away_team
    if normalized in {'draw', 'x', 'tie'} or normalized.endswith('_draw'):
        return 'Empate'
    return raw_value or ''


def oddspapi_collect_h2h_outcomes(bookmaker_payload, event):
    outcomes = {}
    h2h_labels = {
        event.get('participant1Name') or event.get('participant1ShortName') or 'Casa',
        'Empate',
        event.get('participant2Name') or event.get('participant2ShortName') or 'Visitante',
    }

    for market in bookmaker_payload.get('markets', {}).values():
        market_outcomes = {}
        for outcome_key, outcome in market.get('outcomes', {}).items():
            for player in outcome.get('players', {}).values():
                price = player.get('price')
                if price is None or player.get('active') is False:
                    continue
                raw_label = (
                    player.get('bookmakerOutcomeId')
                    or outcome.get('name')
                    or outcome.get('outcomeName')
                    or outcome_key
                )
                label = oddspapi_outcome_label(str(raw_label), event)
                if label not in h2h_labels:
                    continue
                market_outcomes[label] = float(price)
                break
        if len(market_outcomes) >= 2:
            outcomes.update(market_outcomes)
            if len(outcomes) >= 3:
                break
    return outcomes


def build_oddspapi_event_odds_board(event, allowed_bookmaker_terms=None):
    allowed_bookmaker_terms = [
        normalize_bookmaker_text(term)
        for term in (allowed_bookmaker_terms or [])
        if normalize_bookmaker_text(term)
    ]
    home_team = event.get('participant1Name') or event.get('participant1ShortName') or 'Casa'
    away_team = event.get('participant2Name') or event.get('participant2ShortName') or 'Visitante'
    outcome_names = [home_team, 'Empate', away_team]
    bookmakers = []

    for slug, bookmaker_payload in sorted((event.get('bookmakerOdds') or {}).items()):
        normalized_slug = normalize_bookmaker_text(slug)
        if allowed_bookmaker_terms and normalized_slug not in allowed_bookmaker_terms:
            continue
        outcomes = oddspapi_collect_h2h_outcomes(bookmaker_payload, event)
        if not outcomes:
            continue
        bookmakers.append(
            {
                'key': slug,
                'title': slug,
                'last_update': event.get('updatedAt') or '',
                'outcomes': outcomes,
            }
        )

    starts_at = parse_datetime(event.get('startTime') or '') if event.get('startTime') else None
    return {
        'event': f'{home_team} x {away_team}'.strip(' x'),
        'sport': event.get('tournamentName') or event.get('sportName') or '',
        'commence_time': event.get('startTime') or '',
        'outcome_names': outcome_names,
        'bookmakers': bookmakers,
        'filter_note': '',
        'provider': 'oddspapi',
        'display_date': timezone.localtime(starts_at).strftime('%d/%m/%Y %H:%M') if starts_at else '',
    }


def oddspapi_event_to_standard_event(event, allowed_bookmaker_terms=None):
    board = build_oddspapi_event_odds_board(
        event,
        allowed_bookmaker_terms=allowed_bookmaker_terms,
    )
    bookmakers = []
    for bookmaker in board['bookmakers']:
        outcomes = [
            {
                'name': outcome_name,
                'price': price,
            }
            for outcome_name, price in bookmaker['outcomes'].items()
        ]
        bookmakers.append(
            {
                'key': bookmaker['key'],
                'title': bookmaker['title'],
                'last_update': bookmaker['last_update'],
                'markets': [
                    {
                        'key': 'h2h',
                        'outcomes': outcomes,
                    }
                ],
            }
        )
    return {
        'id': event.get('fixtureId'),
        'home_team': event.get('participant1Name') or event.get('participant1ShortName') or '',
        'away_team': event.get('participant2Name') or event.get('participant2ShortName') or '',
        'sport_key': str(event.get('sportId') or ''),
        'sport_title': event.get('tournamentName') or event.get('sportName') or '',
        'commence_time': event.get('startTime') or '',
        'bookmakers': bookmakers,
    }


def user_bets(user):
    return Bet.objects.filter(Q(bankroll__owner=user) | Q(entity__owner=user)).distinct()


@login_required
def event_autocomplete(request):
    odds_api_key = os.environ.get('THE_ODDS_API_KEY')
    oddspapi_key = get_oddspapi_api_key()
    query = (request.GET.get('q') or '').strip().lower()
    sport_text = request.GET.get('sport') or ''
    competition_text = request.GET.get('competition') or ''

    if not odds_api_key and not oddspapi_key:
        return JsonResponse(
            {'results': [], 'error': 'Configure THE_ODDS_API_KEY ou ODDSPAPI_API_KEY.'},
            status=503,
        )

    sport_keys = guess_event_sports(sport_text, competition_text)
    events = []
    from_time, to_time = oddspapi_fixture_window()

    if oddspapi_key:
        client = OddsPapiClient(oddspapi_key)
        for sport_key in sport_keys:
            sport_id = oddspapi_sport_id(sport_key)
            cache_key = f'oddspapi:fixtures:{sport_id}:{from_time}:{to_time}'
            sport_events = cache.get(cache_key)
            if sport_events is None:
                try:
                    sport_events = client.fixtures(
                        sport_id=sport_id,
                        from_time=from_time,
                        to_time=to_time,
                        status_id=0,
                        has_odds=True,
                    )
                except OddsApiError:
                    sport_events = []
                cache.set(cache_key, sport_events, EVENT_SEARCH_CACHE_TIMEOUT)
            events.extend(normalize_oddspapi_event(event, sport_key=sport_key) for event in sport_events)

    if odds_api_key:
        client = OddsApiClient(odds_api_key)
        for sport_key in sport_keys:
            cache_key = f'the_odds_api:events:{sport_key}'
            sport_events = cache.get(cache_key)
            if sport_events is None:
                try:
                    sport_events = client.events(sport_key)
                except OddsApiError:
                    sport_events = []
                cache.set(cache_key, sport_events, EVENT_SEARCH_CACHE_TIMEOUT)
            events.extend({**normalize_event(event), 'sport_key': sport_key} for event in sport_events)

    if query:
        events = [
            event
            for event in events
            if query in event['game'].lower() or query in event['competition'].lower()
        ]

    events = [event for event in events if event['game']]
    events.sort(key=lambda item: item['event_date'] or '9999')
    return JsonResponse({'results': events[:12]})


@login_required
def event_odds(request):
    form_data = request.GET.copy()
    sport_key = (form_data.get('sport_key') or '').strip()
    if sport_key and sport_key in dict(EventOddsForm.base_fields['sport'].choices):
        form_data['event_odds-sport'] = sport_key

    form = EventOddsForm(form_data, prefix='event_odds')
    if not form.is_valid():
        return JsonResponse({'error': 'Filtros inválidos.', 'errors': form.errors}, status=400)

    event_id = (request.GET.get('event_id') or '').strip()
    sport_key = (sport_key or form.cleaned_data['sport']).strip()
    if not event_id or not sport_key:
        return JsonResponse({'error': 'Selecione um jogo antes de buscar odds.'}, status=400)

    bookmakers = crawler_bookmakers_for_request(form.cleaned_data)
    home_team = (request.GET.get('home_team') or '').strip()
    away_team = (request.GET.get('away_team') or '').strip()
    start_time = (request.GET.get('event_date') or '').strip()
    if not home_team or not away_team:
        return JsonResponse({'error': 'Selecione um jogo da lista antes de buscar odds.'}, status=400)

    event = build_crawler_event_payload(
        external_event_id=event_id,
        home_team=home_team,
        away_team=away_team,
        start_time=start_time,
        bookmakers=bookmakers,
    )
    cache_key = (
        'crawler:event_odds:resultado_final:'
        f'{event_id}:{",".join(bookmakers)}'
    )
    snapshot_ids = cache.get(cache_key)
    used_cache = snapshot_ids is not None
    snapshots = latest_event_odds(event_id)
    if not snapshots.exists() and snapshot_ids is None:
        capture_event_odds(event, bookmakers=bookmakers, markets=['Resultado Final'])
        snapshots = latest_event_odds(event_id)
        cache.set(cache_key, list(snapshots.values_list('id', flat=True)), ODDS_CACHE_TIMEOUT)

    board = build_crawler_event_odds_board(event, snapshots, used_cache=used_cache)
    board['bookmaker_filter'] = ','.join(bookmakers)
    board['regions_used'] = 'crawler'
    board['uses_regulated_aliases'] = True
    return JsonResponse(board)


@never_cache
@login_required
def index(request):
    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'preferences':
            preference = ensure_user_preference(request.user)
            preference_form = UserPreferenceForm(request.POST, instance=preference)
            if preference_form.is_valid():
                preference_form.save()
                messages.success(request, 'Configurações salvas com sucesso.')
                return redirect(f'{reverse("dashboard:index")}#settings')
            context = build_dashboard_context(request, preference_form=preference_form)
            return render(request, 'dashboard/index.html', context)

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
                messages.success(request, 'Movimentação registrada.')
                return redirect('dashboard:index')
            context = build_dashboard_context(request, transaction_form=transaction_form)
            return render(request, 'dashboard/index.html', context)

        if form_type == 'bank_account':
            bank_account_form = BankAccountForm(request.POST)
            if bank_account_form.is_valid():
                bank_account = bank_account_form.save(commit=False)
                bank_account.owner = request.user
                bank_account.save()
                messages.success(request, 'Conta bancária cadastrada com sucesso.')
                return redirect('dashboard:index')
            context = build_dashboard_context(request, bank_account_form=bank_account_form)
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
                        note=f'Transferência para {target.name}',
                    )
                    BankrollTransaction.objects.create(
                        bankroll=target,
                        kind=BankrollTransaction.Kind.TRANSFER_IN,
                        amount=amount,
                        note=f'Transferência de {source.name}',
                    )
                messages.success(request, 'Transferência registrada.')
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

        if form_type == 'regulated_bookmaker':
            regulated_form = RegulatedBookmakerForm(request.POST)
            if regulated_form.is_valid():
                bookmaker = regulated_form.save(commit=False)
                bookmaker.owner = request.user
                bookmaker.last_checked_at = timezone.now()
                bookmaker.save()
                messages.success(request, 'Casa regulamentada cadastrada.')
                return redirect(f'{reverse("dashboard:index")}#promotions')
            context = build_dashboard_context(request, regulated_form=regulated_form)
            return render(request, 'dashboard/index.html', context)

        if form_type == 'regulated_import':
            regulated_import_form = RegulatedImportForm(request.POST)
            if regulated_import_form.is_valid():
                imported, updated, errors = import_regulated_bookmakers_from_text(
                    request.user,
                    regulated_import_form.cleaned_data.get('raw_text') or '',
                )
                if imported or updated:
                    messages.success(request, f'{imported} casa(s) importada(s), {updated} atualizada(s).')
                if not imported and not updated and not errors:
                    messages.warning(request, 'Cole a lista no formato empresa;cnpj;marca;dominio;status.')
                for error in errors:
                    messages.error(request, error)
                return redirect(f'{reverse("dashboard:index")}#promotions')
            context = build_dashboard_context(request, regulated_import_form=regulated_import_form)
            return render(request, 'dashboard/index.html', context)

        if form_type == 'bookmaker_alias':
            alias_form = BookmakerAliasForm(request.POST, user=request.user)
            if alias_form.is_valid():
                alias_form.save()
                messages.success(request, 'Alias cadastrado.')
                return redirect(f'{reverse("dashboard:index")}#promotions')
            context = build_dashboard_context(request, alias_form=alias_form)
            return render(request, 'dashboard/index.html', context)

        if form_type == 'promotion_page':
            promotion_page_form = PromotionPageForm(request.POST, user=request.user)
            if promotion_page_form.is_valid():
                page = promotion_page_form.save(commit=False)
                page.last_scan_at = timezone.now()
                page.last_scan_note = 'Página cadastrada para varredura pública.'
                page.save()
                messages.success(request, 'Página pública de promoção cadastrada.')
                return redirect(f'{reverse("dashboard:index")}#promotions')
            context = build_dashboard_context(request, promotion_page_form=promotion_page_form)
            return render(request, 'dashboard/index.html', context)

        if form_type == 'promotion_scan':
            result = scan_user_promotion_pages(request.user, timeout=8, rendered=True)
            messages.success(
                request,
                (
                    f'Varredura concluída: {result["pages"]} página(s), '
                    f'{result["created"]} promoção(ões) nova(s), {result["updated"]} atualizada(s), '
                    f'{result["expired"]} expirada(s), {result["skipped"]} ignorada(s).'
                ),
            )
            for error in result['errors'][:5]:
                messages.warning(request, error)
            return redirect(f'{reverse("dashboard:index")}#promotions')

        if form_type == 'promotion':
            promotion_form = PromotionForm(request.POST, user=request.user)
            if promotion_form.is_valid():
                promotion_form.save()
                messages.success(request, 'Promoção cadastrada.')
                return redirect(f'{reverse("dashboard:index")}#promotions')
            context = build_dashboard_context(request, promotion_form=promotion_form)
            return render(request, 'dashboard/index.html', context)

        if form_type == 'promotion_extraction':
            promotion_extraction_form = PromotionExtractionForm(request.POST, user=request.user)
            if promotion_extraction_form.is_valid():
                result = calculate_promotion_extraction(
                    promotion_extraction_form.cleaned_data['promotion'],
                    promotion_extraction_form.cleaned_data['freebet_odd'],
                    promotion_extraction_form.cleaned_data['protection_odd'],
                    promotion_extraction_form.cleaned_data.get('protection_commission') or Decimal('0.00'),
                )
                context = build_dashboard_context(
                    request,
                    promotion_extraction_form=promotion_extraction_form,
                    promotion_extraction_result=result,
                )
                return render(request, 'dashboard/index.html', context)
            context = build_dashboard_context(request, promotion_extraction_form=promotion_extraction_form)
            return render(request, 'dashboard/index.html', context)

        if form_type == 'odds_search':
            odds_form = OddsSearchForm(request.POST)
            odds_opportunities = []
            odds_comparisons = []
            if odds_form.is_valid():
                bookmakers = crawler_bookmakers_for_request(odds_form.cleaned_data)
                captured_since = timezone.now() - timedelta(hours=12)
                snapshots = OddsSnapshot.objects.filter(
                    market='Resultado Final',
                    captured_at__gte=captured_since,
                )
                if bookmakers:
                    snapshots = snapshots.filter(bookmaker__in=bookmakers)
                events = build_standard_events_from_snapshots(snapshots)
                if not events:
                    messages.warning(
                        request,
                        'Nenhuma odd capturada pelo crawler nas últimas 12 horas.',
                    )
                else:
                    odds_opportunities = detect_surebets(
                        events,
                        limit=odds_form.cleaned_data['limit'],
                        brazil_regulated_only=False,
                    )
                    odds_comparisons = build_odds_comparison(
                        events,
                        limit=odds_form.cleaned_data['limit'],
                        brazil_regulated_only=False,
                    )
                    odds_opportunities = add_suggested_stakes(
                        odds_opportunities,
                        odds_form.cleaned_data['stake'],
                    )
                    if odds_opportunities:
                        messages.success(
                            request,
                            f'{len(odds_opportunities)} oportunidade(s) encontrada(s).',
                        )
                    else:
                        messages.warning(request, 'Nenhuma arbitragem encontrada nos snapshots capturados.')
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

        if form_type == 'freebet_manual':
            freebet_errors = []
            bookmaker = (request.POST.get('manual_freebet_bookmaker') or '').strip()
            amount = decimal_from_post(request.POST, 'manual_freebet_amount', default='')

            if not bookmaker:
                freebet_errors.append('Informe a casa da freebet.')
            if amount is None or amount <= 0:
                freebet_errors.append('Informe um valor de freebet maior que zero.')

            if freebet_errors:
                context = build_dashboard_context(
                    request,
                    freebet_manual_errors=freebet_errors,
                    freebet_manual_data=request.POST,
                )
                return render(request, 'dashboard/index.html', context)

            FreeBet.objects.create(
                owner=request.user,
                bookmaker=bookmaker,
                amount=amount.quantize(Decimal('0.01')),
            )
            messages.success(request, 'Freebet avulsa adicionada.')
            return redirect(f'{reverse("dashboard:index")}#new-bet')

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
            external_event_id = (request.POST.get('surebet_external_event_id') or '').strip()
            external_sport_key = (request.POST.get('surebet_external_sport_key') or '').strip()
            home_team = (request.POST.get('surebet_home_team') or '').strip()
            away_team = (request.POST.get('surebet_away_team') or '').strip()
            event_date = event_date_from_post(request.POST, 'surebet_event_date')
            notes = (request.POST.get('surebet_notes') or '').strip()

            if entity is None:
                surebet_errors.append('Selecione uma entidade válida.')
            if len(outcomes) < 2:
                surebet_errors.append('Informe pelo menos dois resultados de arbitragem.')
            bind_outcome_bankrolls(outcomes, request.user, surebet_errors, entity=entity)

            for outcome in outcomes:
                if outcome['odd'] is None or outcome['odd'] <= 1:
                    surebet_errors.append(f'A odd de {outcome["label"]} precisa ser maior que 1.00.')
                if outcome['stake'] is None or outcome['stake'] <= 0:
                    surebet_errors.append(f'O valor de {outcome["label"]} precisa ser maior que zero.')
                for field, label in [
                    ('commission', 'comissão'),
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
                total_stake = sum(
                    (
                        outcome['liability'] if outcome['mode'] == 'lay' else outcome['stake']
                        for outcome in outcomes
                    ),
                    start=Decimal('0.00'),
                )
                outcome_results = [
                    {
                        **outcome,
                        'return': (outcome['stake'] * outcome['payout_multiplier']).quantize(Decimal('0.01')),
                    }
                    for outcome in outcomes
                ]
                for outcome in outcome_results:
                    losing_cashback = sum(
                        (
                            other['stake'] * (other['cashback'] / Decimal('100'))
                            for other in outcome_results
                            if other is not outcome and other['mode'] == 'back'
                        ),
                        start=Decimal('0.00'),
                    )
                    scenario_net = outcome['return'] - total_stake
                    outcome['cashback_return'] = losing_cashback.quantize(Decimal('0.01'))
                    calculated_net = (scenario_net + outcome['cashback_return']).quantize(Decimal('0.01'))
                    outcome['net'] = (
                        outcome['manual_net_result']
                        if outcome['manual_net_result'] is not None else calculated_net
                    )
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
            market = 'Arbitragem: ' + ' / '.join(outcome['label'] for outcome in outcome_results)
            protection_lines = [
                'Arbitragem cadastrada:',
                f'Responsabilidade total: {format_money(total_stake)}',
            ]
            for outcome in outcome_results:
                protection_lines.append(
                    (
                        f'{outcome["bookmaker"]} - {outcome["label"]}: odd {outcome["odd"]}, '
                        f'modo {outcome["mode"].upper()}, '
                        f'comissão {outcome["commission"]}%, cashback {outcome["cashback"]}%, '
                        f'aumento {outcome["boost"]}%, '
                        f'aposta {format_money(outcome["stake"])}, '
                        f'responsabilidade {format_money(outcome["liability"])}, '
                        f'retorno {format_money(outcome["return"])}, '
                        f'cashback no cenário {format_money(outcome["cashback_return"])}, '
                        f'resultado líquido {format_money(outcome["net"])}'
                        + (
                            f', gera freebet de {format_money(outcome["freebet_amount"])} '
                            f'({freebet_trigger_label(outcome["freebet_trigger"])})'
                            if outcome['freebet_enabled'] else ''
                        )
                    )
                )
            if notes:
                protection_lines.extend(['Observações:', notes])

            bet = Bet.objects.create(
                bankroll=None,
                entity=entity,
                sport=sport,
                competition=competition,
                game=game,
                external_event_id=external_event_id,
                external_sport_key=external_sport_key,
                home_team=home_team,
                away_team=away_team,
                market=market[:120],
                strategy='Arbitragem',
                event_date=event_date,
                odds=effective_odd,
                stake=total_stake,
                exchange_commission=Decimal('0.00'),
                status=Bet.Status.OPEN,
                notes='\n'.join(protection_lines),
            )
            for outcome in outcome_results:
                SureBetEntry.objects.create(
                    bet=bet,
                    bankroll=outcome['bankroll'],
                    bookmaker=outcome['bookmaker'],
                    label=outcome['label'],
                    mode=outcome['mode'],
                    odds=outcome['odd'],
                    effective_odds=outcome['effective_odd_display'],
                    stake=outcome['stake'],
                    liability=outcome['liability'],
                    commission=outcome['commission'],
                    cashback=outcome['cashback'],
                    boost=outcome['boost'],
                    return_amount=outcome['return'],
                    cashback_return=outcome['cashback_return'],
                    net_result=outcome['net'],
                    is_freebet_source=False,
                    freebet_enabled=outcome['freebet_enabled'],
                    freebet_amount=outcome['freebet_amount'],
                    freebet_trigger=outcome['freebet_trigger'],
                    notes=outcome['notes'],
                )
            messages.success(request, 'Arbitragem cadastrada com sucesso.')
            return redirect('dashboard:index')

        if form_type == 'freebet_extract':
            extraction_errors = []
            freebet_id = request.POST.get('freebet_source')
            source_freebet = None
            if freebet_id:
                source_freebet = FreeBet.objects.filter(
                    Q(owner=request.user)
                    | Q(source_bet__bankroll__owner=request.user)
                    | Q(source_bet__entity__owner=request.user),
                    pk=freebet_id,
                    is_used=False,
                ).select_related('source_bet', 'source_bet__entity', 'source_bet__bankroll').first()

            outcomes = build_freebet_extract_payload(request.POST, source_freebet)
            game = (request.POST.get('freebet_game') or '').strip()
            sport = (request.POST.get('freebet_sport') or 'Futebol').strip()
            competition = (request.POST.get('freebet_competition') or '').strip()
            external_event_id = (request.POST.get('freebet_external_event_id') or '').strip()
            external_sport_key = (request.POST.get('freebet_external_sport_key') or '').strip()
            home_team = (request.POST.get('freebet_home_team') or '').strip()
            away_team = (request.POST.get('freebet_away_team') or '').strip()
            event_date = event_date_from_post(request.POST, 'freebet_event_date')
            notes = (request.POST.get('freebet_general_notes') or '').strip()

            if source_freebet is None:
                extraction_errors.append('Selecione uma freebet disponível para extrair.')
            if not game:
                extraction_errors.append('Informe o jogo da extração da freebet.')
            if len(outcomes) < 2:
                extraction_errors.append('Informe a freebet e pelo menos uma arbitragem.')
            bind_outcome_bankrolls(outcomes, request.user, extraction_errors)

            for outcome in outcomes:
                if outcome['odd'] is None or outcome['odd'] <= 1:
                    extraction_errors.append(f'A odd de {outcome["label"]} precisa ser maior que 1.00.')
                if outcome['stake'] is None or outcome['stake'] <= 0:
                    extraction_errors.append(f'O valor de {outcome["label"]} precisa ser maior que zero.')
                for field, label in [
                    ('commission', 'comissão'),
                    ('cashback', 'cashback'),
                    ('boost', 'aumento'),
                ]:
                    if outcome[field] < 0 or outcome[field] > 100:
                        extraction_errors.append(
                            f'O campo {label} de {outcome["label"]} precisa ficar entre 0% e 100%.'
                        )
                if outcome['freebet_enabled'] and outcome['freebet_amount'] <= 0:
                    extraction_errors.append(
                        f'Informe o valor da freebet gerada em {outcome["label"]}.'
                    )

            if not extraction_errors:
                cash_exposure, outcome_results = calculate_freebet_results(outcomes)

            if extraction_errors:
                context = build_dashboard_context(
                    request,
                    freebet_extract_errors=extraction_errors,
                    freebet_extract_data=request.POST,
                )
                return render(request, 'dashboard/index.html', context)

            best_return = max((outcome['return'] for outcome in outcome_results), default=Decimal('0.00'))
            effective_odd = (
                (best_return / cash_exposure).quantize(Decimal('0.01'))
                if cash_exposure > 0 else Decimal('1.00')
            )
            entity = (
                source_freebet.source_bet.entity
                if source_freebet and source_freebet.source_bet else None
            )
            if entity is None and source_freebet and source_freebet.source_bet and source_freebet.source_bet.bankroll:
                entity = source_freebet.source_bet.bankroll.entity
            if entity is None:
                entity = next(
                    (
                        outcome['bankroll'].entity
                        for outcome in outcome_results
                        if outcome.get('bankroll') and outcome['bankroll'].entity_id
                    ),
                    None,
                )
            market = 'Extração freebet: ' + ' / '.join(outcome['label'] for outcome in outcome_results)
            protection_lines = [
                'Extração de freebet cadastrada com arbitragem:',
                f'Freebet usada: {source_freebet.bookmaker} - {format_money(source_freebet.amount)}',
                f'Responsabilidade em dinheiro: {format_money(cash_exposure)}',
            ]
            for outcome in outcome_results:
                prefix = 'FREEBET' if outcome['is_freebet_source'] else outcome['mode'].upper()
                protection_lines.append(
                    (
                        f'{outcome["bookmaker"]} - {outcome["label"]}: odd {outcome["odd"]}, '
                        f'modo {prefix}, comissão {outcome["commission"]}%, '
                        f'cashback {outcome["cashback"]}%, aumento {outcome["boost"]}%, '
                        f'aposta {format_money(outcome["stake"])}, '
                        f'responsabilidade {format_money(Decimal("0.00") if outcome["is_freebet_source"] else outcome["liability"] if outcome["mode"] == "lay" else outcome["stake"])}, '
                        f'retorno {format_money(outcome["return"])}, '
                        f'cashback no cenário {format_money(outcome["cashback_return"])}, '
                        f'resultado líquido {format_money(outcome["net"])}'
                        + (
                            f', gera freebet de {format_money(outcome["freebet_amount"])} '
                            f'({freebet_trigger_label(outcome["freebet_trigger"])})'
                            if outcome['freebet_enabled'] else ''
                        )
                    )
                )
            if notes:
                protection_lines.extend(['Observações:', notes])

            with transaction.atomic():
                bet = Bet.objects.create(
                    bankroll=None,
                    entity=entity,
                    sport=sport,
                    competition=competition,
                    game=game,
                    external_event_id=external_event_id,
                    external_sport_key=external_sport_key,
                    home_team=home_team,
                    away_team=away_team,
                    market=market[:120],
                    strategy='Extração de freebet',
                    event_date=event_date,
                    odds=effective_odd,
                    stake=cash_exposure,
                    exchange_commission=Decimal('0.00'),
                    status=Bet.Status.OPEN,
                    notes='\n'.join(protection_lines),
                )
                for outcome in outcome_results:
                    SureBetEntry.objects.create(
                        bet=bet,
                        bankroll=outcome['bankroll'],
                        bookmaker=outcome['bookmaker'],
                        label=outcome['label'],
                        mode=outcome['mode'],
                        odds=outcome['odd'],
                        effective_odds=outcome['effective_odd_display'],
                        stake=outcome['stake'],
                        liability=outcome['liability'],
                        commission=outcome['commission'],
                        cashback=outcome['cashback'],
                        boost=outcome['boost'],
                        return_amount=outcome['return'],
                        cashback_return=outcome['cashback_return'],
                        net_result=outcome['net'],
                        is_freebet_source=outcome['is_freebet_source'],
                        freebet_enabled=outcome['freebet_enabled'],
                        freebet_amount=outcome['freebet_amount'],
                        notes=(
                            f'Freebet de origem #{source_freebet.pk}. {outcome["notes"]}'.strip()
                            if outcome['is_freebet_source'] else outcome['notes']
                        ),
                    )
                source_freebet.is_used = True
                source_freebet.extraction_bet = bet
                source_freebet.save(update_fields=['is_used', 'extraction_bet'])

            messages.success(request, 'Extração de freebet cadastrada com sucesso.')
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
    if is_protection_bet(bet):
        is_freebet_edit = bet.strategy == 'Extração de freebet'
        current_source_freebet = FreeBet.objects.filter(extraction_bet=bet).first()
        source_freebets = FreeBet.objects.filter(
            Q(owner=request.user)
            | Q(source_bet__bankroll__owner=request.user)
            | Q(source_bet__entity__owner=request.user)
            | Q(extraction_bet=bet),
        ).filter(Q(is_used=False) | Q(extraction_bet=bet)).select_related('source_bet').distinct()
        errors = []

        if request.method == 'POST':
            winner_signature = selected_winner_signature(bet, request.POST.get('winner_entry'))
            if is_freebet_edit:
                freebet_id = request.POST.get('freebet_source')
                source_freebet = None
                if freebet_id:
                    source_freebet = source_freebets.filter(pk=freebet_id).first()
                outcomes = build_freebet_extract_payload(request.POST, source_freebet)
                game = (request.POST.get('freebet_game') or '').strip()
                sport = (request.POST.get('freebet_sport') or 'Futebol').strip()
                competition = (request.POST.get('freebet_competition') or '').strip()
                event_date = event_date_from_post(request.POST, 'freebet_event_date')
                notes = (request.POST.get('freebet_general_notes') or '').strip()

                if source_freebet is None:
                    errors.append('Selecione a freebet usada nessa extração.')
                if not game:
                    errors.append('Informe o jogo da extração da freebet.')
                if len(outcomes) < 2:
                    errors.append('Informe a freebet e pelo menos uma arbitragem.')
                bind_outcome_bankrolls(outcomes, request.user, errors)
                for outcome in outcomes:
                    if outcome['odd'] is None or outcome['odd'] <= 1:
                        errors.append(f'A odd de {outcome["label"]} precisa ser maior que 1.00.')
                    if outcome['stake'] is None or outcome['stake'] <= 0:
                        errors.append(f'O valor de {outcome["label"]} precisa ser maior que zero.')
                    for field, label in [('commission', 'comissão'), ('cashback', 'cashback'), ('boost', 'aumento')]:
                        if outcome[field] < 0 or outcome[field] > 100:
                            errors.append(f'O campo {label} de {outcome["label"]} precisa ficar entre 0% e 100%.')

                if not errors:
                    cash_exposure, outcome_results = calculate_freebet_results(outcomes)
                    best_return = max((outcome['return'] for outcome in outcome_results), default=Decimal('0.00'))
                    effective_odd = (
                        (best_return / cash_exposure).quantize(Decimal('0.01'))
                        if cash_exposure > 0 else Decimal('1.00')
                    )
                    entity = bet.entity
                    if source_freebet and source_freebet.source_bet:
                        entity = source_freebet.source_bet.entity or (
                            source_freebet.source_bet.bankroll.entity
                            if source_freebet.source_bet.bankroll else None
                        )
                    if entity is None:
                        entity = next(
                            (
                                outcome['bankroll'].entity
                                for outcome in outcome_results
                                if outcome.get('bankroll') and outcome['bankroll'].entity_id
                            ),
                            None,
                        )
                    with transaction.atomic():
                        bet.entity = entity
                        bet.bankroll = None
                        bet.sport = sport
                        bet.competition = competition
                        bet.game = game
                        bet.external_event_id = (request.POST.get('freebet_external_event_id') or '').strip()
                        bet.external_sport_key = (request.POST.get('freebet_external_sport_key') or '').strip()
                        bet.home_team = (request.POST.get('freebet_home_team') or '').strip()
                        bet.away_team = (request.POST.get('freebet_away_team') or '').strip()
                        bet.market = ('Extração freebet: ' + ' / '.join(o['label'] for o in outcome_results))[:120]
                        bet.strategy = 'Extração de freebet'
                        bet.event_date = event_date
                        bet.odds = effective_odd
                        bet.stake = cash_exposure
                        bet.exchange_commission = Decimal('0.00')
                        bet.notes = notes
                        bet.save()
                        bet.surebet_entries.all().delete()
                        for outcome in outcome_results:
                            SureBetEntry.objects.create(
                                bet=bet,
                                bankroll=outcome['bankroll'],
                                bookmaker=outcome['bookmaker'],
                                label=outcome['label'],
                                mode=outcome['mode'],
                                odds=outcome['odd'],
                                effective_odds=outcome['effective_odd_display'],
                                stake=outcome['stake'],
                                liability=outcome['liability'],
                                commission=outcome['commission'],
                                cashback=outcome['cashback'],
                                boost=outcome['boost'],
                                return_amount=outcome['return'],
                                cashback_return=outcome['cashback_return'],
                                net_result=outcome['net'],
                                is_freebet_source=outcome['is_freebet_source'],
                                freebet_enabled=outcome['freebet_enabled'],
                                freebet_amount=outcome['freebet_amount'],
                                notes=outcome['notes'],
                            )
                        if current_source_freebet and current_source_freebet.pk != source_freebet.pk:
                            current_source_freebet.is_used = False
                            current_source_freebet.extraction_bet = None
                            current_source_freebet.save(update_fields=['is_used', 'extraction_bet'])
                        source_freebet.is_used = True
                        source_freebet.extraction_bet = bet
                        source_freebet.save(update_fields=['is_used', 'extraction_bet'])
                        winner = find_winner_by_signature(
                            bet.surebet_entries.select_related('bankroll').all(),
                            winner_signature,
                        )
                        if winner:
                            apply_manual_protection_winner(
                                bet,
                                bet.surebet_entries.select_related('bankroll').all(),
                                winner,
                                request.user,
                            )
                    messages.success(request, 'Extração de freebet atualizada.')
                    return redirect(f'{reverse("dashboard:index")}#bets')
                rows = build_freebet_extract_rows(request.POST)
                data = request.POST
            else:
                entity_id = request.POST.get('surebet_entity')
                entity = Entity.objects.filter(owner=request.user, pk=entity_id).first() if entity_id else None
                outcomes = build_surebet_payload(request.POST)
                game = (request.POST.get('surebet_game') or '').strip()
                sport = (request.POST.get('surebet_sport') or 'Futebol').strip()
                competition = (request.POST.get('surebet_competition') or '').strip()
                event_date = event_date_from_post(request.POST, 'surebet_event_date')
                notes = (request.POST.get('surebet_general_notes') or '').strip()

                if entity is None:
                    errors.append('Selecione a entidade da arbitragem.')
                if not game:
                    errors.append('Informe o jogo da arbitragem.')
                if len(outcomes) < 2:
                    errors.append('Informe pelo menos dois resultados de arbitragem.')
                bind_outcome_bankrolls(outcomes, request.user, errors, entity=entity)
                for outcome in outcomes:
                    if outcome['odd'] is None or outcome['odd'] <= 1:
                        errors.append(f'A odd de {outcome["label"]} precisa ser maior que 1.00.')
                    if outcome['stake'] is None or outcome['stake'] <= 0:
                        errors.append(f'O valor de {outcome["label"]} precisa ser maior que zero.')
                    for field, label in [('commission', 'comissão'), ('cashback', 'cashback'), ('boost', 'aumento')]:
                        if outcome[field] < 0 or outcome[field] > 100:
                            errors.append(f'O campo {label} de {outcome["label"]} precisa ficar entre 0% e 100%.')
                    if outcome['freebet_enabled'] and outcome['freebet_amount'] <= 0:
                        errors.append(f'Informe o valor da freebet gerada em {outcome["label"]}.')

                if not errors:
                    total_stake, outcome_results = calculate_protection_results(outcomes)
                    best_return = max((outcome['return'] for outcome in outcome_results), default=total_stake)
                    effective_odd = (best_return / total_stake).quantize(Decimal('0.01')) if total_stake > 0 else Decimal('1.00')
                    with transaction.atomic():
                        bet.entity = entity
                        bet.bankroll = None
                        bet.sport = sport
                        bet.competition = competition
                        bet.game = game
                        bet.external_event_id = (request.POST.get('surebet_external_event_id') or '').strip()
                        bet.external_sport_key = (request.POST.get('surebet_external_sport_key') or '').strip()
                        bet.home_team = (request.POST.get('surebet_home_team') or '').strip()
                        bet.away_team = (request.POST.get('surebet_away_team') or '').strip()
                        bet.market = ('Arbitragem: ' + ' / '.join(o['label'] for o in outcome_results))[:120]
                        bet.strategy = 'Arbitragem'
                        bet.event_date = event_date
                        bet.odds = effective_odd
                        bet.stake = total_stake
                        bet.exchange_commission = Decimal('0.00')
                        bet.notes = notes
                        bet.save()
                        bet.surebet_entries.all().delete()
                        for outcome in outcome_results:
                            SureBetEntry.objects.create(
                                bet=bet,
                                bankroll=outcome['bankroll'],
                                bookmaker=outcome['bookmaker'],
                                label=outcome['label'],
                                mode=outcome['mode'],
                                odds=outcome['odd'],
                                effective_odds=outcome['effective_odd_display'],
                                stake=outcome['stake'],
                                liability=outcome['liability'],
                                commission=outcome['commission'],
                                cashback=outcome['cashback'],
                                boost=outcome['boost'],
                                return_amount=outcome['return'],
                                cashback_return=outcome['cashback_return'],
                                net_result=outcome['net'],
                                freebet_enabled=outcome['freebet_enabled'],
                                freebet_amount=outcome['freebet_amount'],
                                freebet_trigger=outcome['freebet_trigger'],
                                notes=outcome['notes'],
                            )
                        winner = find_winner_by_signature(
                            bet.surebet_entries.select_related('bankroll').all(),
                            winner_signature,
                        )
                        if winner:
                            apply_manual_protection_winner(
                                bet,
                                bet.surebet_entries.select_related('bankroll').all(),
                                winner,
                                request.user,
                            )
                    messages.success(request, 'Arbitragem atualizada.')
                    return redirect(f'{reverse("dashboard:index")}#bets')
                rows = build_surebet_rows(request.POST)
                data = request.POST
        else:
            if is_freebet_edit:
                data = freebet_data_from_bet(bet, current_source_freebet)
                rows = rows_from_surebet_entries(bet, 'freebet')
            else:
                data = surebet_data_from_bet(bet)
                rows = rows_from_surebet_entries(bet, 'surebet')

        context = {
            'bet': bet,
            'is_freebet_edit': is_freebet_edit,
            'errors': errors,
            'entities': Entity.objects.filter(owner=request.user),
            'bankrolls': Bankroll.objects.filter(owner=request.user).select_related('entity'),
            'available_freebet_list': source_freebets,
            'freebet_extract_data': data if is_freebet_edit else {},
            'freebet_extract_rows': rows if is_freebet_edit else [],
            'surebet_data': data if not is_freebet_edit else {},
            'surebet_rows': rows if not is_freebet_edit else [],
            'entries': bet.surebet_entries.select_related('bankroll').all(),
        }
        return render(request, 'dashboard/complex_bet_form.html', context)

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
            messages.success(request, 'Configurações da banca atualizadas.')
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
def edit_bank_account(request, pk):
    bank_account = get_object_or_404(BankAccount, pk=pk, owner=request.user)
    if request.method == 'POST':
        form = BankAccountForm(request.POST, instance=bank_account)
        if form.is_valid():
            form.save()
            messages.success(request, 'Conta bancária atualizada.')
            return redirect('dashboard:index')
    else:
        form = BankAccountForm(instance=bank_account)

    return render(
        request,
        'dashboard/bank_account_form.html',
        {
            'form': form,
            'bank_account': bank_account,
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
                f'Banca "{name}" excluída com {bet_count} aposta(s) vinculada(s).',
            )
        else:
            messages.success(request, f'Banca "{name}" excluída com sucesso.')
    return redirect('dashboard:index')


@login_required
def edit_transaction(request, pk):
    bankroll_transaction = get_object_or_404(
        BankrollTransaction,
        pk=pk,
        bankroll__owner=request.user,
    )
    if request.method == 'POST':
        form = BankrollTransactionForm(
            request.POST,
            instance=bankroll_transaction,
            user=request.user,
        )
        if form.is_valid():
            form.save()
            messages.success(request, 'Movimentação atualizada.')
            return redirect('dashboard:index')
    else:
        form = BankrollTransactionForm(instance=bankroll_transaction, user=request.user)

    return render(
        request,
        'dashboard/transaction_form.html',
        {
            'form': form,
            'transaction': bankroll_transaction,
        },
    )


@login_required
def delete_transaction(request, pk):
    bankroll_transaction = get_object_or_404(
        BankrollTransaction,
        pk=pk,
        bankroll__owner=request.user,
    )
    if request.method == 'POST':
        bankroll_transaction.delete()
        messages.success(request, 'Movimentação excluída.')
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
                f'Entidade "{name}" excluída com {bankroll_count} banca(s) '
                f'e {bet_count} aposta(s) vinculada(s).'
            ),
        )
    return redirect('dashboard:index')


@login_required
def settle_bet(request, pk, status):
    bet = get_object_or_404(user_bets(request.user), pk=pk)
    if is_protection_bet(bet):
        messages.error(request, 'Use a finalização da arbitragem para escolher a casa vencedora.')
        return redirect('dashboard:settle_surebet', pk=bet.pk)
    if request.method == 'POST' and status in {Bet.Status.WON, Bet.Status.LOST, Bet.Status.OPEN}:
        bet.status = status
        if status == Bet.Status.OPEN:
            bet.actual_net_result = None
            bet.save(update_fields=['status', 'actual_net_result'])
        else:
            bet.save(update_fields=['status'])
        messages.success(request, 'Status da aposta atualizado.')
    return redirect_to_history()


@login_required
def cashout_bet(request, pk):
    bet = get_object_or_404(user_bets(request.user), pk=pk)
    if is_protection_bet(bet):
        messages.error(request, 'Use a finalização da arbitragem para escolher a casa vencedora.')
        return redirect('dashboard:settle_surebet', pk=bet.pk)

    if request.method == 'POST':
        cashout_result = decimal_from_post(request.POST, 'cashout_result', default='')
        if cashout_result is None:
            messages.error(request, 'Informe um valor válido para o lucro ou prejuízo do cash out.')
            return redirect_to_history()

        cashout_result = cashout_result.quantize(Decimal('0.01'))
        bet.status = Bet.Status.WON if cashout_result >= 0 else Bet.Status.LOST
        bet.actual_net_result = cashout_result
        bet.exact_score = 'Cash out'
        bet.save(update_fields=['status', 'actual_net_result', 'exact_score'])
        messages.success(request, 'Cash out registrado com sucesso.')

    return redirect_to_history()


@login_required
def settle_surebet(request, pk):
    bet = get_object_or_404(
        user_bets(request.user).prefetch_related('surebet_entries', 'generated_freebets'),
        pk=pk,
        strategy__in=PROTECTION_STRATEGIES,
    )
    entries = bet.surebet_entries.select_related('bankroll').all()

    if request.method == 'POST':
        entry_id = request.POST.get('winner_entry')
        winner = entries.filter(pk=entry_id).first() if entry_id else None
        if winner is None:
            messages.error(request, 'Selecione a casa vencedora da arbitragem.')
            return render(
                request,
                'dashboard/surebet_settle.html',
                {'bet': bet, 'entries': entries},
            )

        apply_manual_protection_winner(bet, entries, winner, request.user)

        messages.success(request, 'Arbitragem finalizada com o resultado da casa vencedora.')
        return redirect_to_history()

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
        messages.success(request, 'Aposta excluída.')
    return redirect_to_history()


@login_required
def bankroll_detail(request, pk):
    bankroll = get_object_or_404(
        Bankroll.objects.prefetch_related('bets', 'transactions'),
        pk=pk,
        owner=request.user,
    )
    bets = bankroll.bets.select_related('bankroll')[:50]
    transactions = bankroll.transactions.all()[:50]
    goals = MonthlyGoal.objects.filter(entity=bankroll.entity)[:12] if bankroll.entity else []
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
            UserAccess.create_trial_for(user)
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
