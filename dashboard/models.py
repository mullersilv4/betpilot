from django.conf import settings
from django.db import models
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

MONEY_PLACES = Decimal('0.01')


class Bet(models.Model):
    class Status(models.TextChoices):
        OPEN = 'open', 'Aberta'
        WON = 'won', 'Ganha'
        LOST = 'lost', 'Perdida'

    class EntryType(models.TextChoices):
        PRE_MATCH = 'pre_match', 'Pre-live'
        LIVE = 'live', 'Ao vivo'

    bankroll = models.ForeignKey(
        'Bankroll',
        verbose_name='banca',
        related_name='bets',
        on_delete=models.PROTECT,
        null=True,
    )
    entity = models.ForeignKey(
        'Entity',
        verbose_name='entidade',
        related_name='bets',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    sport = models.CharField('esporte', max_length=60, blank=True, default='Futebol')
    competition = models.CharField('competicao', max_length=120, blank=True)
    game = models.CharField('jogo', max_length=160)
    external_event_id = models.CharField('id externo do evento', max_length=80, blank=True)
    external_sport_key = models.CharField('sport key externo', max_length=80, blank=True)
    home_team = models.CharField('mandante', max_length=120, blank=True)
    away_team = models.CharField('visitante', max_length=120, blank=True)
    market = models.CharField('mercado', max_length=120)
    strategy = models.CharField('estrategia/tipster', max_length=120, blank=True)
    event_date = models.DateTimeField('data do evento', null=True, blank=True)
    entry_type = models.CharField(
        'tipo de entrada',
        max_length=12,
        choices=EntryType.choices,
        default=EntryType.PRE_MATCH,
    )
    odds = models.DecimalField('odd', max_digits=8, decimal_places=2)
    stake = models.DecimalField('valor apostado', max_digits=10, decimal_places=2)
    exchange_commission = models.DecimalField(
        'comissao da exchange (%)',
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    status = models.CharField(
        'resultado',
        max_length=8,
        choices=Status.choices,
        default=Status.OPEN,
    )
    exact_score = models.CharField('resultado exato', max_length=40, blank=True)
    game_link = models.URLField('link do jogo', blank=True)
    notes = models.TextField('observacoes', blank=True)
    actual_net_result = models.DecimalField(
        'resultado liquido real',
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField('criada em', default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'aposta'
        verbose_name_plural = 'apostas'

    def __str__(self):
        return f'{self.game} - {self.market}'

    @property
    def gross_profit(self):
        return (self.stake * (self.odds - Decimal('1.00'))).quantize(MONEY_PLACES)

    @property
    def commission_amount(self):
        if self.exchange_commission <= 0:
            return Decimal('0.00')
        return (self.gross_profit * (self.exchange_commission / Decimal('100'))).quantize(
            MONEY_PLACES
        )

    @property
    def potential_profit(self):
        return (self.gross_profit - self.commission_amount).quantize(MONEY_PLACES)

    @property
    def potential_return(self):
        return (self.stake + self.potential_profit).quantize(MONEY_PLACES)

    @property
    def net_result(self):
        if self.status != self.Status.OPEN and self.actual_net_result is not None:
            return self.actual_net_result
        if self.status == self.Status.WON:
            return self.potential_profit
        if self.status == self.Status.LOST:
            return self.stake * Decimal('-1')
        return Decimal('0.00')

    @property
    def roi(self):
        if self.stake == 0:
            return Decimal('0.00')
        return (self.net_result / self.stake) * Decimal('100')


class FreeBet(models.Model):
    source_bet = models.ForeignKey(
        Bet,
        verbose_name='aposta de origem',
        related_name='generated_freebets',
        on_delete=models.CASCADE,
    )
    bookmaker = models.CharField('casa de aposta', max_length=80)
    amount = models.DecimalField('valor', max_digits=10, decimal_places=2)
    is_used = models.BooleanField('utilizada', default=False)
    created_at = models.DateTimeField('criada em', default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'freebet'
        verbose_name_plural = 'freebets'

    def __str__(self):
        return f'{self.bookmaker} - R$ {self.amount}'


class SureBetEntry(models.Model):
    bet = models.ForeignKey(
        Bet,
        verbose_name='surebet',
        related_name='surebet_entries',
        on_delete=models.CASCADE,
    )
    bookmaker = models.CharField('casa de aposta', max_length=80)
    label = models.CharField('tipo/resultado', max_length=80)
    odds = models.DecimalField('odd', max_digits=8, decimal_places=2)
    effective_odds = models.DecimalField('odd efetiva', max_digits=8, decimal_places=2)
    stake = models.DecimalField('valor apostado', max_digits=10, decimal_places=2)
    commission = models.DecimalField('comissao (%)', max_digits=5, decimal_places=2, default=Decimal('0.00'))
    cashback = models.DecimalField('cashback (%)', max_digits=5, decimal_places=2, default=Decimal('0.00'))
    boost = models.DecimalField('aumento (%)', max_digits=5, decimal_places=2, default=Decimal('0.00'))
    return_amount = models.DecimalField('retorno', max_digits=12, decimal_places=2)
    cashback_return = models.DecimalField('cashback no cenario', max_digits=12, decimal_places=2, default=Decimal('0.00'))
    net_result = models.DecimalField('resultado liquido', max_digits=12, decimal_places=2)
    freebet_enabled = models.BooleanField('gera freebet', default=False)
    freebet_amount = models.DecimalField('valor da freebet', max_digits=10, decimal_places=2, default=Decimal('0.00'))
    is_winner = models.BooleanField('entrada vencedora', default=False)
    created_at = models.DateTimeField('criada em', default=timezone.now)

    class Meta:
        ordering = ['id']
        verbose_name = 'entrada de surebet'
        verbose_name_plural = 'entradas de surebet'

    def __str__(self):
        return f'{self.bookmaker} - {self.label}'


class BankrollTransaction(models.Model):
    class Kind(models.TextChoices):
        DEPOSIT = 'deposit', 'Deposito'
        WITHDRAW = 'withdraw', 'Saque'
        ADJUSTMENT = 'adjustment', 'Ajuste'
        TRANSFER_IN = 'transfer_in', 'Transferencia entrada'
        TRANSFER_OUT = 'transfer_out', 'Transferencia saida'

    bankroll = models.ForeignKey(
        'Bankroll',
        verbose_name='banca',
        related_name='transactions',
        on_delete=models.CASCADE,
    )
    kind = models.CharField('tipo', max_length=16, choices=Kind.choices)
    amount = models.DecimalField('valor', max_digits=12, decimal_places=2)
    note = models.CharField('observacao', max_length=160, blank=True)
    created_at = models.DateTimeField('criada em', default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'movimentacao'
        verbose_name_plural = 'movimentacoes'

    def __str__(self):
        return f'{self.get_kind_display()} - {self.bankroll}'

    @property
    def signed_amount(self):
        if self.kind in {self.Kind.WITHDRAW, self.Kind.TRANSFER_OUT}:
            return self.amount * Decimal('-1')
        return self.amount


class Entity(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='usuario',
        related_name='entities',
        on_delete=models.CASCADE,
    )
    name = models.CharField('nome', max_length=100)
    notes = models.CharField('observacao', max_length=160, blank=True)
    created_at = models.DateTimeField('criada em', default=timezone.now)

    class Meta:
        ordering = ['name']
        unique_together = ('owner', 'name')
        verbose_name = 'entidade'
        verbose_name_plural = 'entidades'

    def __str__(self):
        return self.name


class Bankroll(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='usuario',
        related_name='bankrolls',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    entity = models.ForeignKey(
        Entity,
        verbose_name='entidade',
        related_name='bankrolls',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    name = models.CharField('nome', max_length=80)
    bookmaker = models.CharField('casa/exchange', max_length=80, blank=True)
    initial_balance = models.DecimalField(
        'saldo inicial',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    unit_percentage = models.DecimalField(
        'unidade padrao (%)',
        max_digits=5,
        decimal_places=2,
        default=Decimal('1.00'),
    )
    max_stake_percentage = models.DecimalField(
        'stake maxima (%)',
        max_digits=5,
        decimal_places=2,
        default=Decimal('10.00'),
    )
    daily_stop_loss_percentage = models.DecimalField(
        'stop loss diario (%)',
        max_digits=5,
        decimal_places=2,
        default=Decimal('5.00'),
    )
    weekly_stop_loss_percentage = models.DecimalField(
        'stop loss semanal (%)',
        max_digits=5,
        decimal_places=2,
        default=Decimal('10.00'),
    )
    monthly_stop_loss_percentage = models.DecimalField(
        'stop loss mensal (%)',
        max_digits=5,
        decimal_places=2,
        default=Decimal('20.00'),
    )
    daily_stop_win_percentage = models.DecimalField(
        'stop win diario (%)',
        max_digits=5,
        decimal_places=2,
        default=Decimal('8.00'),
    )
    created_at = models.DateTimeField('criada em', default=timezone.now)

    class Meta:
        ordering = ['name']
        verbose_name = 'banca'
        verbose_name_plural = 'bancas'

    def __str__(self):
        return self.name

    @property
    def transaction_total(self):
        return sum(
            (transaction.signed_amount for transaction in self.transactions.all()),
            start=Decimal('0.00'),
        )

    @property
    def closed_result(self):
        return sum((bet.net_result for bet in self.bets.all()), start=Decimal('0.00'))

    @property
    def open_exposure(self):
        return sum(
            (bet.stake for bet in self.bets.filter(status=Bet.Status.OPEN)),
            start=Decimal('0.00'),
        )

    @property
    def current_balance(self):
        return (
            self.initial_balance + self.transaction_total + self.closed_result
        ).quantize(MONEY_PLACES)

    @property
    def available_balance(self):
        return (self.current_balance - self.open_exposure).quantize(MONEY_PLACES)

    @property
    def suggested_unit(self):
        return (
            self.current_balance * (self.unit_percentage / Decimal('100'))
        ).quantize(MONEY_PLACES)

    @property
    def max_stake_amount(self):
        return (
            self.current_balance * (self.max_stake_percentage / Decimal('100'))
        ).quantize(MONEY_PLACES)

    @property
    def daily_stop_loss_amount(self):
        return (
            self.current_balance * (self.daily_stop_loss_percentage / Decimal('100'))
        ).quantize(MONEY_PLACES)

    @property
    def weekly_stop_loss_amount(self):
        return (
            self.current_balance * (self.weekly_stop_loss_percentage / Decimal('100'))
        ).quantize(MONEY_PLACES)

    @property
    def monthly_stop_loss_amount(self):
        return (
            self.current_balance * (self.monthly_stop_loss_percentage / Decimal('100'))
        ).quantize(MONEY_PLACES)

    @property
    def daily_stop_win_amount(self):
        return (
            self.current_balance * (self.daily_stop_win_percentage / Decimal('100'))
        ).quantize(MONEY_PLACES)

    def result_since(self, start):
        return sum(
            (
                bet.net_result
                for bet in self.bets.filter(
                    created_at__gte=start,
                ).exclude(status=Bet.Status.OPEN)
            ),
            start=Decimal('0.00'),
        ).quantize(MONEY_PLACES)

    @property
    def today_result(self):
        start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
        return self.result_since(start)

    @property
    def week_result(self):
        now = timezone.localtime()
        start = (now - timedelta(days=now.weekday())).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        return self.result_since(start)

    @property
    def month_result(self):
        start = timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return self.result_since(start)

    @property
    def daily_stop_loss_reached(self):
        return self.today_result <= (self.daily_stop_loss_amount * Decimal('-1'))

    @property
    def weekly_stop_loss_reached(self):
        return self.week_result <= (self.weekly_stop_loss_amount * Decimal('-1'))

    @property
    def monthly_stop_loss_reached(self):
        return self.month_result <= (self.monthly_stop_loss_amount * Decimal('-1'))

    @property
    def daily_stop_win_reached(self):
        return self.today_result >= self.daily_stop_win_amount

    @property
    def risk_lock_active(self):
        return (
            self.daily_stop_loss_reached
            or self.weekly_stop_loss_reached
            or self.monthly_stop_loss_reached
            or self.daily_stop_win_reached
        )

    @property
    def risk_alerts(self):
        alerts = []
        if self.daily_stop_loss_reached:
            alerts.append('Stop loss diario atingido')
        if self.weekly_stop_loss_reached:
            alerts.append('Stop loss semanal atingido')
        if self.monthly_stop_loss_reached:
            alerts.append('Stop loss mensal atingido')
        if self.daily_stop_win_reached:
            alerts.append('Stop win diario atingido')
        if self.open_exposure > self.max_stake_amount:
            alerts.append('Exposicao aberta acima da stake maxima')
        return alerts


class MonthlyGoal(models.Model):
    bankroll = models.ForeignKey(
        Bankroll,
        verbose_name='banca',
        related_name='goals',
        on_delete=models.CASCADE,
    )
    month = models.DateField('mes de referencia')
    profit_target = models.DecimalField(
        'meta de lucro',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    roi_target = models.DecimalField(
        'meta de ROI (%)',
        max_digits=6,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    volume_target = models.PositiveIntegerField('meta de volume', default=0)
    max_loss = models.DecimalField(
        'limite de perda',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    created_at = models.DateTimeField('criada em', default=timezone.now)

    class Meta:
        ordering = ['-month', 'bankroll__name']
        unique_together = ('bankroll', 'month')
        verbose_name = 'meta mensal'
        verbose_name_plural = 'metas mensais'

    def __str__(self):
        return f'{self.bankroll} - {self.month:%m/%Y}'

    @property
    def month_start(self):
        return timezone.datetime(self.month.year, self.month.month, 1, tzinfo=timezone.get_current_timezone())

    @property
    def next_month_start(self):
        if self.month.month == 12:
            return timezone.datetime(self.month.year + 1, 1, 1, tzinfo=timezone.get_current_timezone())
        return timezone.datetime(self.month.year, self.month.month + 1, 1, tzinfo=timezone.get_current_timezone())

    @property
    def settled_bets(self):
        return self.bankroll.bets.filter(
            created_at__gte=self.month_start,
            created_at__lt=self.next_month_start,
        ).exclude(status=Bet.Status.OPEN)

    @property
    def profit(self):
        return sum((bet.net_result for bet in self.settled_bets), start=Decimal('0.00')).quantize(MONEY_PLACES)

    @property
    def stake(self):
        return sum((bet.stake for bet in self.settled_bets), start=Decimal('0.00')).quantize(MONEY_PLACES)

    @property
    def volume(self):
        return self.settled_bets.count()

    @property
    def roi(self):
        if self.stake == 0:
            return Decimal('0.00')
        return (self.profit / self.stake * Decimal('100')).quantize(Decimal('0.01'))

    def progress_percent(self, current, target):
        if not target or target <= 0:
            return 0
        return min(float(current / target * Decimal('100')), 100)

    @property
    def profit_progress(self):
        return self.progress_percent(max(self.profit, Decimal('0.00')), self.profit_target)

    @property
    def roi_progress(self):
        return self.progress_percent(max(self.roi, Decimal('0.00')), self.roi_target)

    @property
    def volume_progress(self):
        if not self.volume_target:
            return 0
        return min(self.volume / self.volume_target * 100, 100)

    @property
    def loss_used_percent(self):
        if self.max_loss <= 0 or self.profit >= 0:
            return 0
        return min(float(abs(self.profit) / self.max_loss * Decimal('100')), 100)

    @property
    def loss_limit_reached(self):
        return self.max_loss > 0 and self.profit <= (self.max_loss * Decimal('-1'))
