from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

MONEY_PLACES = Decimal('0.01')
TRIAL_DAYS = 7


class UserAccess(models.Model):
    class Status(models.TextChoices):
        TRIAL = 'trial', 'Teste'
        ACTIVE = 'active', 'Ativa'
        EXPIRED = 'expired', 'Expirada'
        CANCELED = 'canceled', 'Cancelada'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name='usuário',
        related_name='access',
        on_delete=models.CASCADE,
    )
    trial_started_at = models.DateTimeField('início do teste', default=timezone.now)
    trial_ends_at = models.DateTimeField('fim do teste')
    status = models.CharField(
        'status',
        max_length=20,
        choices=Status.choices,
        default=Status.TRIAL,
    )
    subscription_ends_at = models.DateTimeField('fim da assinatura', null=True, blank=True)
    created_at = models.DateTimeField('criado em', default=timezone.now)
    updated_at = models.DateTimeField('atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'acesso do usuário'
        verbose_name_plural = 'acessos dos usuários'

    def __str__(self):
        return f'{self.user} - {self.get_status_display()}'

    @classmethod
    def create_trial_for(cls, user):
        started_at = timezone.now()
        return cls.objects.create(
            user=user,
            trial_started_at=started_at,
            trial_ends_at=started_at + timedelta(days=TRIAL_DAYS),
            status=cls.Status.TRIAL,
        )

    @property
    def is_trial_active(self):
        return self.status == self.Status.TRIAL and timezone.now() <= self.trial_ends_at

    @property
    def is_subscription_active(self):
        return (
            self.status == self.Status.ACTIVE
            and (self.subscription_ends_at is None or timezone.now() <= self.subscription_ends_at)
        )

    @property
    def has_access(self):
        return self.is_subscription_active or self.is_trial_active

    @property
    def days_remaining(self):
        if self.status != self.Status.TRIAL:
            return 0
        remaining = self.trial_ends_at - timezone.now()
        if remaining.total_seconds() <= 0:
            return 0
        return max(1, remaining.days + (1 if remaining.seconds else 0))

    def expire_if_needed(self):
        if self.status == self.Status.TRIAL and timezone.now() > self.trial_ends_at:
            self.status = self.Status.EXPIRED
            self.save(update_fields=['status', 'updated_at'])


def ensure_user_access(user):
    access, _created = UserAccess.objects.get_or_create(
        user=user,
        defaults={
            'trial_started_at': timezone.now(),
            'trial_ends_at': timezone.now() + timedelta(days=TRIAL_DAYS),
            'status': UserAccess.Status.TRIAL,
        },
    )
    access.expire_if_needed()
    return access


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
    competition = models.CharField('competição', max_length=120, blank=True)
    game = models.CharField('jogo', max_length=160)
    external_event_id = models.CharField('id externo do evento', max_length=80, blank=True)
    external_sport_key = models.CharField('sport key externo', max_length=80, blank=True)
    home_team = models.CharField('mandante', max_length=120, blank=True)
    away_team = models.CharField('visitante', max_length=120, blank=True)
    market = models.CharField('mercado', max_length=120)
    strategy = models.CharField('estratégia/tipster', max_length=120, blank=True)
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
        'comissão da exchange (%)',
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
    notes = models.TextField('observações', blank=True)
    actual_net_result = models.DecimalField(
        'resultado líquido real',
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
        null=True,
        blank=True,
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='usuário',
        related_name='manual_freebets',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
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


class RegulatedBookmaker(models.Model):
    class Status(models.TextChoices):
        AUTHORIZED = 'authorized', 'Autorizada'
        STATE = 'state', 'Estadual'
        JUDICIAL_ALERT = 'judicial_alert', 'Alerta judicial'
        INACTIVE = 'inactive', 'Inativa'

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='usuário',
        related_name='regulated_bookmakers',
        on_delete=models.CASCADE,
    )
    company_name = models.CharField('empresa', max_length=160)
    brand = models.CharField('marca', max_length=100)
    cnpj = models.CharField('CNPJ', max_length=24, blank=True)
    domain = models.CharField('domínio oficial', max_length=120)
    status = models.CharField(
        'status',
        max_length=20,
        choices=Status.choices,
        default=Status.AUTHORIZED,
    )
    source = models.CharField('origem', max_length=120, blank=True, default='SPA/MF')
    judicial_alert = models.BooleanField('alerta judicial', default=False)
    alert_note = models.CharField('observação do alerta', max_length=180, blank=True)
    last_checked_at = models.DateTimeField('última verificação', null=True, blank=True)
    created_at = models.DateTimeField('criada em', default=timezone.now)

    class Meta:
        ordering = ['brand', 'domain']
        unique_together = ('owner', 'domain')
        verbose_name = 'casa regulamentada'
        verbose_name_plural = 'casas regulamentadas'

    def __str__(self):
        return f'{self.brand} - {self.domain}'


class BookmakerAlias(models.Model):
    bookmaker = models.ForeignKey(
        RegulatedBookmaker,
        verbose_name='casa regulamentada',
        related_name='aliases',
        on_delete=models.CASCADE,
    )
    provider = models.CharField('provedor', max_length=60, default='the_odds_api')
    alias = models.CharField('nome no provedor', max_length=100)
    provider_key = models.CharField('chave no provedor', max_length=100, blank=True)
    created_at = models.DateTimeField('criado em', default=timezone.now)

    class Meta:
        ordering = ['provider', 'alias']
        unique_together = ('bookmaker', 'provider', 'alias')
        verbose_name = 'alias de casa'
        verbose_name_plural = 'aliases de casas'

    def __str__(self):
        return f'{self.alias} -> {self.bookmaker.brand}'


class BookmakerEventLink(models.Model):
    class Status(models.TextChoices):
        FOUND = 'found', 'Encontrado'
        NOT_FOUND = 'not_found', 'Não encontrado'
        ERROR = 'error', 'Erro'
        STALE = 'stale', 'Desatualizado'

    external_event_id = models.CharField('id externo do evento', max_length=120)
    bookmaker = models.CharField('casa', max_length=80)
    home_team = models.CharField('mandante', max_length=120)
    away_team = models.CharField('visitante', max_length=120)
    event_url = models.URLField('URL do evento', max_length=1000, blank=True)
    matched_confidence = models.DecimalField(
        'confiança do match',
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    status = models.CharField(
        'status',
        max_length=40,
        choices=Status.choices,
        default=Status.NOT_FOUND,
    )
    last_error = models.CharField('último erro', max_length=220, blank=True)
    last_checked_at = models.DateTimeField('última verificação', null=True, blank=True)
    created_at = models.DateTimeField('criado em', default=timezone.now)

    class Meta:
        ordering = ['bookmaker', '-last_checked_at']
        unique_together = ('external_event_id', 'bookmaker')
        verbose_name = 'link de evento por casa'
        verbose_name_plural = 'links de eventos por casa'

    def __str__(self):
        return f'{self.bookmaker} - {self.home_team} x {self.away_team}'


class OddsSnapshot(models.Model):
    external_event_id = models.CharField('id externo do evento', max_length=120)
    bookmaker = models.CharField('casa', max_length=80)
    market = models.CharField('mercado', max_length=80)
    selection = models.CharField('seleção', max_length=120)
    odd = models.DecimalField('odd', max_digits=8, decimal_places=3)
    source_url = models.URLField('URL fonte', max_length=1000, blank=True)
    captured_at = models.DateTimeField('capturada em', default=timezone.now)

    class Meta:
        ordering = ['-captured_at']
        indexes = [
            models.Index(fields=['external_event_id', 'market', '-captured_at']),
            models.Index(fields=['bookmaker', '-captured_at']),
        ]
        verbose_name = 'snapshot de odd'
        verbose_name_plural = 'snapshots de odds'

    def __str__(self):
        return f'{self.bookmaker} - {self.market} - {self.selection}: {self.odd}'


class PromotionPage(models.Model):
    bookmaker = models.ForeignKey(
        RegulatedBookmaker,
        verbose_name='casa regulamentada',
        related_name='promotion_pages',
        on_delete=models.CASCADE,
    )
    url = models.URLField('URL pública')
    is_active = models.BooleanField('ativa', default=True)
    last_scan_at = models.DateTimeField('última varredura', null=True, blank=True)
    last_scan_note = models.CharField('nota da última varredura', max_length=180, blank=True)
    created_at = models.DateTimeField('criada em', default=timezone.now)

    class Meta:
        ordering = ['bookmaker__brand', 'url']
        unique_together = ('bookmaker', 'url')
        verbose_name = 'página de promoção'
        verbose_name_plural = 'páginas de promoção'

    def __str__(self):
        return self.url


class Promotion(models.Model):
    class Kind(models.TextChoices):
        FREEBET = 'freebet', 'Freebet'
        CASHBACK = 'cashback', 'Cashback'
        ODDS_BOOST = 'odds_boost', 'Odd turbinada'
        BONUS = 'bonus', 'Bônus'

    class Trigger(models.TextChoices):
        LOST = 'lost', 'Se perder'
        WON = 'won', 'Se ganhar'
        ANY = 'any', 'Ambas'

    class SourceType(models.TextChoices):
        OFFICIAL = 'official', 'Site oficial'
        AFFILIATE = 'affiliate', 'Agregador/afiliado'
        MANUAL = 'manual', 'Manual'

    class ValidationStatus(models.TextChoices):
        CONFIRMED_OFFICIAL = 'confirmed_official', 'Confirmada no site oficial'
        FOUND_AFFILIATE = 'found_affiliate', 'Encontrada em afiliado'
        PENDING = 'pending_validation', 'Pendente de validação'
        EXPIRED = 'expired', 'Expirada'

    bookmaker = models.ForeignKey(
        RegulatedBookmaker,
        verbose_name='casa regulamentada',
        related_name='promotions',
        on_delete=models.CASCADE,
    )
    page = models.ForeignKey(
        PromotionPage,
        verbose_name='página',
        related_name='promotions',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    title = models.CharField('título', max_length=160)
    kind = models.CharField('tipo', max_length=16, choices=Kind.choices, default=Kind.FREEBET)
    trigger = models.CharField('quando gera', max_length=8, choices=Trigger.choices, default=Trigger.LOST)
    freebet_amount = models.DecimalField('valor da freebet', max_digits=10, decimal_places=2, default=Decimal('0.00'))
    min_odd = models.DecimalField('odd mínima', max_digits=8, decimal_places=2, default=Decimal('1.01'))
    sport = models.CharField('esporte', max_length=60, blank=True, default='Futebol')
    competition = models.CharField('competição', max_length=120, blank=True)
    suggested_game = models.CharField('jogo sugerido', max_length=160, blank=True)
    public_text = models.TextField('texto público', blank=True)
    rule_summary = models.CharField('resumo da regra', max_length=220, blank=True)
    source_url = models.URLField('URL da promoção', blank=True)
    source_type = models.CharField('tipo de fonte', max_length=16, choices=SourceType.choices, default=SourceType.OFFICIAL)
    source_name = models.CharField('nome da fonte', max_length=120, blank=True)
    validation_status = models.CharField(
        'status de validação',
        max_length=24,
        choices=ValidationStatus.choices,
        default=ValidationStatus.CONFIRMED_OFFICIAL,
    )
    expires_at = models.DateTimeField('expira em', null=True, blank=True)
    is_active = models.BooleanField('ativa', default=True)
    detected_at = models.DateTimeField('detectada em', default=timezone.now)
    updated_at = models.DateTimeField('atualizada em', auto_now=True)

    class Meta:
        ordering = ['-detected_at']
        verbose_name = 'promoção'
        verbose_name_plural = 'promoções'

    def __str__(self):
        return f'{self.bookmaker.brand} - {self.title}'


class SureBetEntry(models.Model):
    class FreeBetTrigger(models.TextChoices):
        WON = 'won', 'Se ganhar'
        LOST = 'lost', 'Se perder'
        ANY = 'any', 'Em ambos os casos'

    class Mode(models.TextChoices):
        BACK = 'back', 'Back'
        LAY = 'lay', 'Lay'

    bet = models.ForeignKey(
        Bet,
        verbose_name='surebet',
        related_name='surebet_entries',
        on_delete=models.CASCADE,
    )
    bankroll = models.ForeignKey(
        'Bankroll',
        verbose_name='banca',
        related_name='surebet_entries',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    bookmaker = models.CharField('casa de aposta', max_length=80)
    label = models.CharField('tipo/resultado', max_length=80)
    mode = models.CharField(
        'modo',
        max_length=4,
        choices=Mode.choices,
        default=Mode.BACK,
    )
    odds = models.DecimalField('odd', max_digits=8, decimal_places=2)
    effective_odds = models.DecimalField('odd efetiva', max_digits=8, decimal_places=2)
    stake = models.DecimalField('valor apostado', max_digits=10, decimal_places=2)
    liability = models.DecimalField(
        'responsabilidade',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    commission = models.DecimalField('comissão (%)', max_digits=5, decimal_places=2, default=Decimal('0.00'))
    cashback = models.DecimalField('cashback (%)', max_digits=5, decimal_places=2, default=Decimal('0.00'))
    boost = models.DecimalField('aumento (%)', max_digits=5, decimal_places=2, default=Decimal('0.00'))
    return_amount = models.DecimalField('retorno', max_digits=12, decimal_places=2)
    cashback_return = models.DecimalField('cashback no cenário', max_digits=12, decimal_places=2, default=Decimal('0.00'))
    net_result = models.DecimalField('resultado líquido', max_digits=12, decimal_places=2)
    is_freebet_source = models.BooleanField('entrada da freebet usada', default=False)
    freebet_enabled = models.BooleanField('gera freebet', default=False)
    freebet_amount = models.DecimalField('valor da freebet', max_digits=10, decimal_places=2, default=Decimal('0.00'))
    freebet_trigger = models.CharField(
        'quando gera freebet',
        max_length=8,
        choices=FreeBetTrigger.choices,
        default=FreeBetTrigger.WON,
    )
    notes = models.CharField('observação', max_length=180, blank=True)
    is_winner = models.BooleanField('entrada vencedora', default=False)
    created_at = models.DateTimeField('criada em', default=timezone.now)

    class Meta:
        ordering = ['id']
        verbose_name = 'entrada de surebet'
        verbose_name_plural = 'entradas de surebet'

    def __str__(self):
        return f'{self.bookmaker} - {self.label}'

    @property
    def exposure(self):
        if self.is_freebet_source:
            return Decimal('0.00')
        if self.mode == self.Mode.LAY:
            return self.liability
        return self.stake

    def settlement_result_for(self, winner):
        if self.pk == winner.pk:
            if self.is_freebet_source:
                return self.return_amount.quantize(MONEY_PLACES)
            return (self.return_amount - self.exposure).quantize(MONEY_PLACES)
        if self.is_freebet_source:
            return Decimal('0.00')
        cashback_return = Decimal('0.00')
        if self.mode == self.Mode.BACK and self.cashback > 0:
            cashback_return = self.stake * (self.cashback / Decimal('100'))
        return (cashback_return - self.exposure).quantize(MONEY_PLACES)


class BankrollTransaction(models.Model):
    class Kind(models.TextChoices):
        DEPOSIT = 'deposit', 'Deposito'
        WITHDRAW = 'withdraw', 'Saque'
        ADJUSTMENT = 'adjustment', 'Ajuste'
        TRANSFER_IN = 'transfer_in', 'Transferência entrada'
        TRANSFER_OUT = 'transfer_out', 'Transferência saida'

    bankroll = models.ForeignKey(
        'Bankroll',
        verbose_name='banca',
        related_name='transactions',
        on_delete=models.CASCADE,
    )
    bet = models.ForeignKey(
        Bet,
        verbose_name='aposta',
        related_name='bankroll_transactions',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    bank_account = models.ForeignKey(
        'BankAccount',
        verbose_name='conta bancária',
        related_name='transactions',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    kind = models.CharField('tipo', max_length=16, choices=Kind.choices)
    amount = models.DecimalField('valor', max_digits=12, decimal_places=2)
    note = models.CharField('observação', max_length=160, blank=True)
    created_at = models.DateTimeField('criada em', default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'movimentação'
        verbose_name_plural = 'movimentações'

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
        verbose_name='usuário',
        related_name='entities',
        on_delete=models.CASCADE,
    )
    name = models.CharField('nome', max_length=100)
    notes = models.CharField('observação', max_length=160, blank=True)
    created_at = models.DateTimeField('criada em', default=timezone.now)

    class Meta:
        ordering = ['name']
        unique_together = ('owner', 'name')
        verbose_name = 'entidade'
        verbose_name_plural = 'entidades'

    def __str__(self):
        return self.name


class BankAccount(models.Model):
    class AccountType(models.TextChoices):
        CHECKING = 'checking', 'Conta corrente'
        SAVINGS = 'savings', 'Poupança'
        PAYMENT = 'payment', 'Conta de pagamento'
        PIX = 'pix', 'Pix'
        OTHER = 'other', 'Outra'

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='usuário',
        related_name='bank_accounts',
        on_delete=models.CASCADE,
    )
    name = models.CharField('apelido', max_length=80)
    bank_name = models.CharField('banco/instituição', max_length=100)
    account_type = models.CharField(
        'tipo',
        max_length=16,
        choices=AccountType.choices,
        default=AccountType.CHECKING,
    )
    agency = models.CharField('agência', max_length=20, blank=True)
    account_number = models.CharField('conta', max_length=40, blank=True)
    pix_key = models.CharField('chave Pix', max_length=120, blank=True)
    notes = models.CharField('observação', max_length=160, blank=True)
    created_at = models.DateTimeField('criada em', default=timezone.now)

    class Meta:
        ordering = ['bank_name', 'name']
        unique_together = ('owner', 'name')
        verbose_name = 'conta bancária'
        verbose_name_plural = 'contas bancárias'

    def __str__(self):
        return f'{self.name} - {self.bank_name}'


class Bankroll(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='usuário',
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
        'unidade padrão (%)',
        max_digits=5,
        decimal_places=2,
        default=Decimal('1.00'),
    )
    max_stake_percentage = models.DecimalField(
        'stake máxima (%)',
        max_digits=5,
        decimal_places=2,
        default=Decimal('10.00'),
    )
    daily_stop_loss_percentage = models.DecimalField(
        'stop loss diário (%)',
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
        'stop win diário (%)',
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
    def display_name(self):
        if not self.bookmaker:
            return self.name
        if self.bookmaker.lower() in self.name.lower():
            return self.name
        return f'{self.name} - {self.bookmaker}'

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
            alerts.append('Stop loss diário atingido')
        if self.weekly_stop_loss_reached:
            alerts.append('Stop loss semanal atingido')
        if self.monthly_stop_loss_reached:
            alerts.append('Stop loss mensal atingido')
        if self.daily_stop_win_reached:
            alerts.append('Stop win diário atingido')
        if self.open_exposure > self.max_stake_amount:
            alerts.append('Exposição aberta acima da stake máxima')
        return alerts


class MonthlyGoal(models.Model):
    entity = models.ForeignKey(
        Entity,
        verbose_name='entidade',
        related_name='goals',
        on_delete=models.CASCADE,
    )
    month = models.DateField('mês de referência')
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
        ordering = ['-month', 'entity__name']
        unique_together = ('entity', 'month')
        verbose_name = 'meta mensal'
        verbose_name_plural = 'metas mensais'

    def __str__(self):
        return f'{self.entity} - {self.month:%m/%Y}'

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
        return Bet.objects.filter(
            Q(entity=self.entity) | Q(bankroll__entity=self.entity),
            created_at__gte=self.month_start,
            created_at__lt=self.next_month_start,
        ).exclude(status=Bet.Status.OPEN).distinct()

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
