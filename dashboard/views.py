from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.db import transaction
from django.db.models import Q
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
from .forms import ImportTextForm
from .forms import MonthlyGoalForm
from .forms import SignUpForm
from .forms import TransferForm
from .models import Bankroll
from .models import BankrollTransaction
from .models import Bet
from .models import MonthlyGoal


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


def ensure_default_bankroll(user):
    Bankroll.objects.filter(owner__isnull=True).update(owner=user)
    bankroll = Bankroll.objects.filter(owner=user, name='Banca principal').first()
    if bankroll is None:
        bankroll = Bankroll.objects.create(
            owner=user,
            name='Banca principal',
            bookmaker='Geral',
            initial_balance=1000,
        )
    Bet.objects.filter(bankroll__isnull=True).update(bankroll=bankroll)
    return bankroll


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
    ensure_default_bankroll(request.user)

    bankrolls = Bankroll.objects.filter(owner=request.user).prefetch_related('bets', 'transactions')
    all_bets = Bet.objects.filter(bankroll__owner=request.user).select_related('bankroll')
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
        'bankroll_form': forms.get('bankroll_form') or BankrollForm(),
        'form': forms.get('bet_form') or BetForm(user=request.user),
        'transaction_form': forms.get('transaction_form') or BankrollTransactionForm(user=request.user),
        'transfer_form': forms.get('transfer_form') or TransferForm(user=request.user),
        'filter_form': filter_form,
        'import_form': forms.get('import_form') or ImportTextForm(),
        'goal_form': forms.get('goal_form') or MonthlyGoalForm(user=request.user),
        'bankrolls': bankrolls,
        'bankroll_risk_data': [
            {
                'id': bankroll.id,
                'unit': float(bankroll.suggested_unit),
                'maxStake': float(bankroll.max_stake_amount),
            }
            for bankroll in bankrolls
        ],
        'risk_alerts': [
            {'bankroll': bankroll, 'message': alert}
            for bankroll in bankrolls
            for alert in bankroll.risk_alerts
        ],
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
        },
        'market_stats': market_stats[:5],
        'chart_values': chart_values,
        'analytics': analytics,
    }


@login_required
def index(request):
    ensure_default_bankroll(request.user)

    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'bankroll':
            bankroll_form = BankrollForm(request.POST)
            if bankroll_form.is_valid():
                bankroll = bankroll_form.save(commit=False)
                bankroll.owner = request.user
                bankroll.save()
                messages.success(request, 'Banca cadastrada com sucesso.')
                return redirect('dashboard:index')
            context = build_dashboard_context(request, bankroll_form=bankroll_form)
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

        if form_type == 'goal':
            goal_form = MonthlyGoalForm(request.POST, user=request.user)
            if goal_form.is_valid():
                goal_form.save()
                messages.success(request, 'Meta mensal salva.')
                return redirect('dashboard:index')
            context = build_dashboard_context(request, goal_form=goal_form)
            return render(request, 'dashboard/index.html', context)

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
    bet = get_object_or_404(Bet, pk=pk, bankroll__owner=request.user)
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
        form = BankrollForm(request.POST, instance=bankroll)
        if form.is_valid():
            form.save()
            messages.success(request, 'Configuracoes da banca atualizadas.')
            return redirect('dashboard:index')
    else:
        form = BankrollForm(instance=bankroll)

    return render(
        request,
        'dashboard/bankroll_form.html',
        {
            'form': form,
            'bankroll': bankroll,
        },
    )


@login_required
def settle_bet(request, pk, status):
    bet = get_object_or_404(Bet, pk=pk, bankroll__owner=request.user)
    if request.method == 'POST' and status in {Bet.Status.WON, Bet.Status.LOST, Bet.Status.OPEN}:
        bet.status = status
        bet.save(update_fields=['status'])
        messages.success(request, 'Status da aposta atualizado.')
    return redirect('dashboard:index')


@login_required
def delete_bet(request, pk):
    bet = get_object_or_404(Bet, pk=pk, bankroll__owner=request.user)
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
            ensure_default_bankroll(user)
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
