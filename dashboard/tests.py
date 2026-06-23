from decimal import Decimal
from datetime import timedelta
import hashlib
import hmac
import json
from unittest.mock import patch
from django.core import mail
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User

from django.test import override_settings
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse

from .analytics import build_analytics
from .analytics import build_month_calendar
from .analytics import max_drawdown
from .automation import import_bets_from_csv
from .automation import import_bets_from_text
from .forms import BankrollForm
from .forms import BankrollTransactionForm
from .forms import BetForm
from .forms import PromotionForm
from .forms import TransferForm
from .models import Bankroll
from .models import BankAccount
from .models import BankrollTransaction
from .models import Bet
from .models import BookmakerAlias
from .models import Entity
from .models import FreeBet
from .models import MonthlyGoal
from .models import Promotion
from .models import PromotionPage
from .models import RegulatedBookmaker
from .models import SureBetEntry
from .models import Payment
from .models import SubscriptionReminder
from .models import UserAccess
from .promotion_scan import detect_money
from .promotion_scan import detect_expires_at
from .promotion_scan import is_actionable_promotion
from .promotion_scan import scan_promotion_page
from .result_settlement import apply_settlement
from .result_settlement import apply_surebet_settlement
from .result_settlement import resolve_bet_from_event
from .result_settlement import resolve_surebet_from_event
from .views import build_surebet_payload
from .views import parse_import_lines


class BetCalculationTests(TestCase):
    def setUp(self):
        self.bankroll = Bankroll.objects.create(
            name='Banca principal',
            bookmaker='Betfair',
            initial_balance=Decimal('1000.00'),
        )

    def test_winning_exchange_bet_discounts_commission_from_profit(self):
        bet = Bet(
            bankroll=self.bankroll,
            game='Palmeiras x Flamengo',
            market='Over 2.5 gols',
            odds=Decimal('1.90'),
            stake=Decimal('100.00'),
            exchange_commission=Decimal('5.00'),
            status=Bet.Status.WON,
        )

        self.assertEqual(bet.gross_profit, Decimal('90.00'))
        self.assertEqual(bet.commission_amount, Decimal('4.50'))
        self.assertEqual(bet.potential_profit, Decimal('85.50'))
        self.assertEqual(bet.potential_return, Decimal('185.50'))
        self.assertEqual(bet.net_result, Decimal('85.50'))

    def test_odds_boost_increases_only_profit_portion(self):
        bet = Bet(
            bankroll=self.bankroll,
            game='Santos x Bahia',
            market='Casa vence',
            odds=Decimal('1.50'),
            stake=Decimal('100.00'),
            odds_boost=Decimal('10.00'),
            status=Bet.Status.WON,
        )

        self.assertEqual(bet.effective_odds, Decimal('1.55'))
        self.assertEqual(bet.gross_profit, Decimal('55.00'))
        self.assertEqual(bet.potential_return, Decimal('155.00'))

    def test_surebet_boost_increases_only_profit_portion(self):
        outcomes = build_surebet_payload(
            {
                'surebet_bookmaker_1': 'Bet365',
                'surebet_outcome_1': 'Casa vence',
                'surebet_mode_1': 'back',
                'surebet_odd_1': '1.50',
                'surebet_stake_1': '100.00',
                'surebet_commission_1': '0',
                'surebet_cashback_1': '0',
                'surebet_boost_1': '10',
            }
        )

        self.assertEqual(outcomes[0]['effective_odd'].quantize(Decimal('0.01')), Decimal('1.55'))
        self.assertEqual(outcomes[0]['payout_multiplier'].quantize(Decimal('0.01')), Decimal('1.55'))

    def test_lost_bet_returns_negative_stake(self):
        bet = Bet(
            bankroll=self.bankroll,
            game='Sinner x Alcaraz',
            market='Total sets 3',
            odds=Decimal('2.30'),
            stake=Decimal('80.00'),
            status=Bet.Status.LOST,
        )

        self.assertEqual(bet.net_result, Decimal('-80.00'))

    def test_bankroll_available_balance_discounts_open_exposure(self):
        Bet.objects.create(
            bankroll=self.bankroll,
            game='Celtics x Knicks',
            market='Handicap -4.5',
            odds=Decimal('1.85'),
            stake=Decimal('200.00'),
            status=Bet.Status.OPEN,
        )

        self.assertEqual(self.bankroll.current_balance, Decimal('1000.00'))
        self.assertEqual(self.bankroll.open_exposure, Decimal('200.00'))
        self.assertEqual(self.bankroll.available_balance, Decimal('800.00'))

    def test_bankroll_balance_includes_deposits_and_withdrawals(self):
        BankrollTransaction.objects.create(
            bankroll=self.bankroll,
            kind=BankrollTransaction.Kind.DEPOSIT,
            amount=Decimal('200.00'),
        )
        BankrollTransaction.objects.create(
            bankroll=self.bankroll,
            kind=BankrollTransaction.Kind.WITHDRAW,
            amount=Decimal('50.00'),
        )

        self.assertEqual(self.bankroll.transaction_total, Decimal('150.00'))
        self.assertEqual(self.bankroll.current_balance, Decimal('1150.00'))

    def test_bankroll_adjustment_sets_exact_current_balance(self):
        BankrollTransaction.objects.create(
            bankroll=self.bankroll,
            kind=BankrollTransaction.Kind.DEPOSIT,
            amount=Decimal('200.00'),
        )

        form = BankrollTransactionForm(
            data={
                'bankroll': self.bankroll.id,
                'kind': BankrollTransaction.Kind.ADJUSTMENT,
                'amount': '900.00',
                'note': '',
            }
        )

        self.assertTrue(form.is_valid())
        form.save()

        self.assertEqual(self.bankroll.current_balance, Decimal('900.00'))


class HistoryFilterRedirectTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='owner', password='StrongPass123!')
        self.bankroll = Bankroll.objects.create(
            owner=self.user,
            name='Banca principal',
            bookmaker='Betfair',
            initial_balance=Decimal('1000.00'),
        )
        self.bet = Bet.objects.create(
            bankroll=self.bankroll,
            game='Palmeiras x Flamengo',
            market='Over 2.5 gols',
            odds=Decimal('1.90'),
            stake=Decimal('100.00'),
            status=Bet.Status.OPEN,
        )

    def test_settle_bet_keeps_history_filter_redirect(self):
        self.client.login(username='owner', password='StrongPass123!')
        next_url = '/?status=open#bets'

        response = self.client.post(
            reverse('dashboard:settle_bet', args=[self.bet.pk, Bet.Status.WON]),
            {'next': next_url},
        )

        self.assertRedirects(response, next_url, fetch_redirect_response=False)
        self.bet.refresh_from_db()
        self.assertEqual(self.bet.status, Bet.Status.WON)


class BetFormTests(TestCase):
    def setUp(self):
        self.bankroll = Bankroll.objects.create(
            name='Banca principal',
            bookmaker='Geral',
            initial_balance=Decimal('100.00'),
        )

    def test_odds_must_be_greater_than_one(self):
        form = BetForm(
            data={
                'bankroll': self.bankroll.id,
                'sport': 'Futebol',
                'game': 'Teste x Exemplo',
                'market': 'Vencedor',
                'entry_type': Bet.EntryType.PRE_MATCH,
                'odds': '1.00',
                'stake': '50.00',
                'exchange_commission': '0',
                'status': Bet.Status.OPEN,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn('odds', form.errors)

    def test_stake_must_fit_available_bankroll_balance(self):
        form = BetForm(
            data={
                'bankroll': self.bankroll.id,
                'sport': 'Futebol',
                'game': 'Teste x Exemplo',
                'market': 'Vencedor',
                'entry_type': Bet.EntryType.PRE_MATCH,
                'odds': '2.00',
                'stake': '120.00',
                'exchange_commission': '0',
                'status': Bet.Status.OPEN,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn('stake', form.errors)


class BankrollFormTests(TestCase):
    def test_bankroll_form_creates_bankroll(self):
        user = User.objects.create_user(username='muller')
        entity = Entity.objects.create(owner=user, name='Muller')
        form = BankrollForm(
            data={
                'entity': entity.id,
                'bookmaker': 'Betfair',
                'initial_balance': '500.00',
            },
            user=user,
        )

        self.assertTrue(form.is_valid())
        bankroll = form.save(commit=False)
        self.assertEqual(bankroll.name, 'Muller - Betfair')


class PromotionFormTests(TestCase):
    def test_page_must_belong_to_same_bookmaker(self):
        user = User.objects.create_user(username='owner')
        betano = RegulatedBookmaker.objects.create(
            owner=user,
            company_name='Kaizen Gaming Brasil',
            brand='Betano',
            domain='betano.bet.br',
        )
        bet365 = RegulatedBookmaker.objects.create(
            owner=user,
            company_name='Hillside Brasil',
            brand='bet365',
            domain='bet365.bet.br',
        )
        page = PromotionPage.objects.create(bookmaker=bet365, url='https://www.bet365.bet.br/promos')
        form = PromotionForm(
            data={
                'bookmaker': betano.id,
                'page': page.id,
                'title': 'Perdeu ganhou freebet',
                'kind': Promotion.Kind.FREEBET,
                'trigger': Promotion.Trigger.LOST,
                'freebet_amount': '50.00',
                'min_odd': '1.80',
                'sport': 'Futebol',
                'competition': '',
                'suggested_game': '',
                'source_url': 'https://www.bet365.bet.br/promos',
                'public_text': '',
                'is_active': 'on',
            },
            user=user,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('page', form.errors)


class PromotionScanTests(TestCase):
    def test_detect_money_supports_brazilian_and_decimal_formats(self):
        self.assertEqual(detect_money('Ganhe R$ 1.000,50 em freebet'), Decimal('1000.50'))
        self.assertEqual(detect_money('Ganhe R$ 50.25 em freebet'), Decimal('50.25'))
        self.assertEqual(detect_money('Ganhe R$ 2.000 em bonus'), Decimal('2000.00'))

    def test_actionable_filter_rejects_navigation_fragments(self):
        self.assertFalse(
            is_actionable_promotion(
                'EXCHANGE TRADEBALL SPORTSBOOK CRIADOR EVENTOS SUPER ODDS CASSINO FERRAMENTAS ACADEMIA ENTRAR CADASTRO'
            )
        )

    def test_detect_expires_at_uses_local_datetime(self):
        expires_at = detect_expires_at('Aposta Grátis Expira: 28/05/2026 19:59 Ganhe uma aposta grátis.')

        self.assertIsNotNone(expires_at)
        self.assertEqual(expires_at.day, 28)
        self.assertEqual(expires_at.hour, 19)
        self.assertTrue(timezone.is_aware(expires_at))
        self.assertTrue(
            is_actionable_promotion(
                'Aposta Grátis em Todo Gol Brasileiro Expira: 28/05/2026 Ganhe uma aposta grátis a cada gol brasileiro.'
            )
        )

    @patch('dashboard.promotion_scan.fetch_scan_text')
    def test_scan_promotion_page_creates_public_promotion(self, mocked_fetch):
        user = User.objects.create_user(username='owner')
        bookmaker = RegulatedBookmaker.objects.create(
            owner=user,
            company_name='Kaizen Gaming Brasil',
            brand='Betano',
            domain='betano.bet.br',
        )
        page = PromotionPage.objects.create(bookmaker=bookmaker, url='https://www.betano.bet.br/promocoes')
        mocked_fetch.return_value = (
            'Perdeu ganhou: aposte em futebol com odd mínima 1,80 e receba freebet de R$ 50,00.',
            'simples',
        )

        result = scan_promotion_page(page)

        self.assertEqual(result['created'], 1)
        promotion = Promotion.objects.get(bookmaker=bookmaker)
        self.assertEqual(promotion.kind, Promotion.Kind.FREEBET)
        self.assertEqual(promotion.trigger, Promotion.Trigger.LOST)
        self.assertEqual(promotion.freebet_amount, Decimal('50.00'))
        self.assertEqual(promotion.min_odd, Decimal('1.80'))
        self.assertEqual(promotion.source_type, Promotion.SourceType.OFFICIAL)
        self.assertEqual(promotion.validation_status, Promotion.ValidationStatus.CONFIRMED_OFFICIAL)
        self.assertIsNone(promotion.expires_at)

    @patch('dashboard.promotion_scan.fetch_scan_text')
    def test_scan_promotion_page_ignores_affiliate_blocks(self, mocked_fetch):
        user = User.objects.create_user(username='owner')
        bookmaker = RegulatedBookmaker.objects.create(
            owner=user,
            company_name='Kaizen Gaming Brasil',
            brand='Betano',
            domain='betano.bet.br',
        )
        page = PromotionPage.objects.create(bookmaker=bookmaker, url='https://www.betano.bet.br/afiliados')
        mocked_fetch.return_value = (
            'Programa de afiliação: indique e ganhe bonus com seus amigos.',
            'simples',
        )

        result = scan_promotion_page(page)

        self.assertEqual(result['created'], 0)
        self.assertFalse(Promotion.objects.exists())

    @patch('dashboard.promotion_scan.fetch_scan_text')
    def test_scan_promotion_page_ignores_generic_navigation(self, mocked_fetch):
        user = User.objects.create_user(username='owner')
        bookmaker = RegulatedBookmaker.objects.create(
            owner=user,
            company_name='Bolsa de Aposta',
            brand='Bolsa de Aposta',
            domain='bolsadeaposta.bet.br',
        )
        page = PromotionPage.objects.create(bookmaker=bookmaker, url='https://bolsadeaposta.bet.br/')
        mocked_fetch.return_value = (
            'EXCHANGE TRADEBALL SPORTSBOOK CRIADOR EVENTOS SUPER ODDS CASSINO FERRAMENTAS ACADEMIA ENTRAR CADASTRO',
            'renderizada',
        )

        result = scan_promotion_page(page)

        self.assertEqual(result['created'], 0)
        self.assertEqual(result['skipped'], 1)
        self.assertFalse(Promotion.objects.exists())

    @patch('dashboard.promotion_scan.fetch_scan_text')
    def test_scan_promotion_page_expires_stale_page_promotions(self, mocked_fetch):
        user = User.objects.create_user(username='owner')
        bookmaker = RegulatedBookmaker.objects.create(
            owner=user,
            company_name='Sportingbet',
            brand='Sportingbet',
            domain='sportingbet.bet.br',
        )
        page = PromotionPage.objects.create(bookmaker=bookmaker, url='https://www.sportingbet.bet.br/promocoes')
        stale = Promotion.objects.create(
            bookmaker=bookmaker,
            page=page,
            title='Menu antigo Promoções Ajuda Entrar',
            source_url=page.url,
            public_text='Menu antigo Promoções Ajuda Entrar',
        )
        mocked_fetch.return_value = (
            'Aposta Grátis em Todo Gol Brasileiro Expira: 28/05/2026 Ganhe uma aposta grátis a cada gol brasileiro.',
            'renderizada',
        )

        result = scan_promotion_page(page)

        stale.refresh_from_db()
        self.assertEqual(result['created'], 1)
        self.assertEqual(result['expired'], 1)
        self.assertFalse(stale.is_active)
        self.assertEqual(stale.validation_status, Promotion.ValidationStatus.EXPIRED)

    @patch('dashboard.promotion_scan.fetch_scan_text')
    def test_scan_promotion_page_saves_expiration_and_rule_summary(self, mocked_fetch):
        user = User.objects.create_user(username='owner')
        bookmaker = RegulatedBookmaker.objects.create(
            owner=user,
            company_name='Sportingbet',
            brand='Sportingbet',
            domain='sportingbet.bet.br',
        )
        page = PromotionPage.objects.create(bookmaker=bookmaker, url='https://www.sportingbet.bet.br/promocoes')
        mocked_fetch.return_value = (
            'Aposta Grátis em Todo Gol Brasileiro Expira: 28/05/2026 19:59 Ganhe uma aposta grátis a cada gol brasileiro.',
            'renderizada',
        )

        scan_promotion_page(page)

        promotion = Promotion.objects.get(bookmaker=bookmaker)
        self.assertEqual(promotion.title, 'Aposta Grátis em Todo Gol Brasileiro')
        self.assertEqual(promotion.expires_at.day, 28)
        self.assertIn('Ganhe uma aposta grátis', promotion.rule_summary)


class AnalyticsTests(TestCase):
    def setUp(self):
        self.bankroll = Bankroll.objects.create(
            name='Banca principal',
            initial_balance=Decimal('1000.00'),
        )

    def test_build_analytics_returns_grouped_roi_and_streak(self):
        now = timezone.localtime().replace(hour=12, minute=0, second=0, microsecond=0)
        Bet.objects.create(
            bankroll=self.bankroll,
            game='Time A x Time B',
            sport='Futebol',
            market='Over 2.5',
            odds=Decimal('2.00'),
            stake=Decimal('50.00'),
            status=Bet.Status.WON,
            created_at=now - timezone.timedelta(hours=3),
        )
        Bet.objects.create(
            bankroll=self.bankroll,
            game='Time C x Time D',
            sport='Futebol',
            market='Over 2.5',
            odds=Decimal('2.00'),
            stake=Decimal('50.00'),
            status=Bet.Status.LOST,
            created_at=now - timezone.timedelta(hours=2),
        )
        Bet.objects.create(
            bankroll=self.bankroll,
            game='Time E x Time F',
            sport='Basquete',
            market='Casa vence',
            odds=Decimal('1.80'),
            stake=Decimal('40.00'),
            status=Bet.Status.WON,
            created_at=now,
        )

        analytics = build_analytics(Bet.objects.select_related('bankroll'), Decimal('1000.00'))

        self.assertEqual(len(analytics['market_rows']), 2)
        self.assertEqual(len(analytics['sport_rows']), 2)
        self.assertEqual(analytics['streak']['label'], 'Vitorias')
        self.assertEqual(analytics['periods'][0]['count'], 3)

    def test_max_drawdown_uses_largest_drop_from_peak(self):
        self.assertEqual(max_drawdown([1000, 1100, 900, 950, 870]), Decimal('-230.00'))

    def test_month_calendar_groups_closed_results_by_day(self):
        reference = timezone.localtime().replace(day=10, hour=12, minute=0, second=0, microsecond=0)
        Bet.objects.create(
            bankroll=self.bankroll,
            game='Time A x Time B',
            market='Over 2.5',
            odds=Decimal('2.00'),
            stake=Decimal('50.00'),
            status=Bet.Status.WON,
            created_at=reference,
        )
        Bet.objects.create(
            bankroll=self.bankroll,
            game='Time C x Time D',
            market='Casa vence',
            odds=Decimal('2.00'),
            stake=Decimal('30.00'),
            status=Bet.Status.LOST,
            created_at=reference,
        )
        Bet.objects.create(
            bankroll=self.bankroll,
            game='Time E x Time F',
            market='Empate',
            odds=Decimal('3.00'),
            stake=Decimal('20.00'),
            status=Bet.Status.OPEN,
            created_at=reference,
        )

        calendar = build_month_calendar(Bet.objects.all(), reference.date())
        days = [day for week in calendar['weeks'] for day in week if day.get('day') == 10]

        self.assertEqual(days[0]['profit'], Decimal('20.00'))
        self.assertEqual(days[0]['count'], 2)
        self.assertEqual(days[0]['tone'], 'positive')

    def test_freebet_extraction_uses_source_bet_settlement_day(self):
        source_day = timezone.localtime().replace(day=7, hour=18, minute=0, second=0, microsecond=0)
        extraction_day = timezone.localtime().replace(day=20, hour=12, minute=0, second=0, microsecond=0)
        source_bet = Bet.objects.create(
            bankroll=self.bankroll,
            game='Time A x Time B',
            market='Promo',
            odds=Decimal('2.00'),
            stake=Decimal('50.00'),
            status=Bet.Status.WON,
            settled_at=source_day,
            created_at=source_day - timezone.timedelta(days=1),
        )
        extraction_bet = Bet.objects.create(
            bankroll=self.bankroll,
            game='Time C x Time D',
            market='Extração freebet',
            strategy='Extração de freebet',
            odds=Decimal('1.50'),
            stake=Decimal('100.00'),
            status=Bet.Status.WON,
            actual_net_result=Decimal('30.00'),
            created_at=extraction_day,
        )
        FreeBet.objects.create(
            source_bet=source_bet,
            extraction_bet=extraction_bet,
            bookmaker='Casa teste',
            amount=Decimal('25.00'),
            is_used=True,
        )

        calendar = build_month_calendar(Bet.objects.select_related(
            'extracted_freebet',
            'extracted_freebet__source_bet',
        ), source_day.date())
        day_7 = [day for week in calendar['weeks'] for day in week if day.get('day') == 7][0]
        day_20 = [day for week in calendar['weeks'] for day in week if day.get('day') == 20][0]

        self.assertEqual(day_7['profit'], Decimal('80.00'))
        self.assertEqual(day_7['count'], 2)
        self.assertEqual(day_20['profit'], Decimal('0.00'))
        self.assertEqual(day_20['count'], 0)


class BankrollTransactionFormTests(TestCase):
    def setUp(self):
        self.bankroll = Bankroll.objects.create(
            name='Banca principal',
            initial_balance=Decimal('100.00'),
        )

    def test_withdraw_cannot_exceed_available_balance(self):
        form = BankrollTransactionForm(
            data={
                'bankroll': self.bankroll.id,
                'kind': BankrollTransaction.Kind.WITHDRAW,
                'amount': '120.00',
                'note': '',
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn('amount', form.errors)

    def test_edit_adjustment_keeps_amount_as_exact_target_balance(self):
        adjustment = BankrollTransaction.objects.create(
            bankroll=self.bankroll,
            kind=BankrollTransaction.Kind.ADJUSTMENT,
            amount=Decimal('50.00'),
        )
        form = BankrollTransactionForm(
            data={
                'bankroll': self.bankroll.id,
                'kind': BankrollTransaction.Kind.ADJUSTMENT,
                'amount': '80.00',
                'note': '',
            },
            instance=adjustment,
        )

        self.assertTrue(form.is_valid())
        form.save()

        self.assertEqual(self.bankroll.current_balance, Decimal('80.00'))

    def test_delete_transaction_removes_movement(self):
        user = User.objects.create_user(username='owner', password='StrongPass123!')
        bankroll = Bankroll.objects.create(
            owner=user,
            name='Minha banca',
            initial_balance=Decimal('100.00'),
        )
        movement = BankrollTransaction.objects.create(
            bankroll=bankroll,
            kind=BankrollTransaction.Kind.DEPOSIT,
            amount=Decimal('25.00'),
        )

        self.client.login(username='owner', password='StrongPass123!')
        response = self.client.post(reverse('dashboard:delete_transaction', args=[movement.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(BankrollTransaction.objects.filter(pk=movement.pk).exists())

    def test_transfer_requires_different_bankrolls(self):
        form = TransferForm(
            data={
                'source': self.bankroll.id,
                'target': self.bankroll.id,
                'amount': '10.00',
            }
        )

        self.assertFalse(form.is_valid())


class ImportTextTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='testpass123')

    def test_parse_import_lines_creates_valid_bet(self):
        Bankroll.objects.create(name='Banca principal', initial_balance=Decimal('500.00'))

        imported, errors = parse_import_lines(
            'Banca principal;Palmeiras x Flamengo;Over 2.5;1.90;40;5;ganha'
        )

        self.assertEqual(errors, [])
        self.assertEqual(len(imported), 1)
        self.assertEqual(imported[0].status, Bet.Status.WON)

    def test_parse_professional_import_line_creates_context_fields(self):
        Bankroll.objects.create(name='Banca principal', initial_balance=Decimal('500.00'))

        imported, errors = parse_import_lines(
            'Banca principal;Tenis;ATP Roma;Sinner x Alcaraz;Vencedor;Tipster Pro;live;2026-05-13 14:30;1.80;40;0;aberta'
        )

        self.assertEqual(errors, [])
        self.assertEqual(len(imported), 1)
        self.assertEqual(imported[0].sport, 'Tenis')
        self.assertEqual(imported[0].competition, 'ATP Roma')
        self.assertEqual(imported[0].entry_type, Bet.EntryType.LIVE)

    def test_free_text_import_identifies_fields(self):
        Bankroll.objects.create(
            owner=self.user,
            name='Banca principal',
            initial_balance=Decimal('500.00'),
        )

        imported, errors, warnings = import_bets_from_text(
            'banca: Banca principal; jogo: Lakers x Celtics; mercado: Handicap -3.5; odd: 1.91; valor: 40; esporte: Basquete',
            self.user,
        )

        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(len(imported), 1)
        self.assertEqual(imported[0].sport, 'Basquete')

    def test_import_skips_duplicate_open_bet(self):
        bankroll = Bankroll.objects.create(
            owner=self.user,
            name='Banca principal',
            initial_balance=Decimal('500.00'),
        )
        Bet.objects.create(
            bankroll=bankroll,
            game='Lakers x Celtics',
            market='Handicap -3.5',
            odds=Decimal('1.91'),
            stake=Decimal('40.00'),
            status=Bet.Status.OPEN,
        )

        imported, errors, warnings = import_bets_from_text(
            'Banca principal;Lakers x Celtics;Handicap -3.5;1.91;40;0;open',
            self.user,
        )

        self.assertEqual(imported, [])
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 1)

    def test_import_warns_high_odd(self):
        Bankroll.objects.create(
            owner=self.user,
            name='Banca principal',
            initial_balance=Decimal('500.00'),
        )

        imported, errors, warnings = import_bets_from_text(
            'Banca principal;Time A x Time B;Placar exato;8.00;20;0;open',
            self.user,
        )

        self.assertEqual(errors, [])
        self.assertEqual(len(imported), 1)
        self.assertEqual(len(warnings), 1)

    def test_csv_upload_imports_bet(self):
        Bankroll.objects.create(
            owner=self.user,
            name='Banca principal',
            initial_balance=Decimal('500.00'),
        )
        csv_file = SimpleUploadedFile(
            'bets.csv',
            (
                'banca,esporte,competicao,jogo,mercado,odd,valor,status\n'
                'Banca principal,Futebol,Brasileirao,Flamengo x Vasco,Over 2.5,1.90,40,open\n'
            ).encode(),
            content_type='text/csv',
        )

        imported, errors, warnings = import_bets_from_csv(csv_file, self.user)

        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(len(imported), 1)
        self.assertEqual(imported[0].competition, 'Brasileirao')


class MonthlyGoalTests(TestCase):
    def test_monthly_goal_calculates_progress(self):
        user = User.objects.create_user(username='owner', password='StrongPass123!')
        entity = Entity.objects.create(owner=user, name='Operacao A')
        bankroll = Bankroll.objects.create(
            owner=user,
            entity=entity,
            name='Banca principal',
            initial_balance=Decimal('1000.00'),
        )
        Bet.objects.create(
            bankroll=bankroll,
            entity=entity,
            game='Time A x Time B',
            market='Over 2.5',
            odds=Decimal('2.00'),
            stake=Decimal('50.00'),
            status=Bet.Status.WON,
            created_at=timezone.now(),
        )
        goal = MonthlyGoal.objects.create(
            entity=entity,
            month=timezone.localdate().replace(day=1),
            profit_target=Decimal('100.00'),
            roi_target=Decimal('50.00'),
            volume_target=2,
            max_loss=Decimal('80.00'),
        )

        self.assertEqual(goal.profit, Decimal('50.00'))
        self.assertEqual(goal.volume, 1)
        self.assertEqual(goal.profit_progress, 50.0)
        self.assertEqual(goal.volume_progress, 50.0)


class AutomaticSettlementTests(TestCase):
    def setUp(self):
        self.bankroll = Bankroll.objects.create(
            name='Banca principal',
            bookmaker='Betfair',
            initial_balance=Decimal('1000.00'),
        )

    def finished_event(self, home_score='2', away_score='1'):
        return {
            'id': 'event-1',
            'completed': True,
            'home_team': 'Palmeiras',
            'away_team': 'Flamengo',
            'scores': [
                {'name': 'Palmeiras', 'score': home_score},
                {'name': 'Flamengo', 'score': away_score},
            ],
        }

    def make_external_bet(self, market):
        return Bet.objects.create(
            bankroll=self.bankroll,
            sport='Futebol',
            competition='Brasileirao',
            game='Palmeiras x Flamengo',
            external_event_id='event-1',
            external_sport_key='soccer_brazil_campeonato',
            home_team='Palmeiras',
            away_team='Flamengo',
            market=market,
            odds=Decimal('2.00'),
            stake=Decimal('100.00'),
        )

    def make_external_surebet(self):
        bet = Bet.objects.create(
            bankroll=self.bankroll,
            sport='Futebol',
            competition='Brasileirao',
            game='Palmeiras x Flamengo',
            external_event_id='event-1',
            external_sport_key='soccer_brazil_campeonato',
            home_team='Palmeiras',
            away_team='Flamengo',
            market='Surebet: Palmeiras / Empate / Flamengo',
            strategy='Surebet',
            odds=Decimal('1.10'),
            stake=Decimal('300.00'),
        )
        SureBetEntry.objects.create(
            bet=bet,
            bookmaker='Bet365',
            label='Palmeiras',
            odds=Decimal('2.00'),
            effective_odds=Decimal('2.00'),
            stake=Decimal('100.00'),
            return_amount=Decimal('200.00'),
            net_result=Decimal('10.00'),
        )
        SureBetEntry.objects.create(
            bet=bet,
            bookmaker='Betfair',
            label='Empate',
            odds=Decimal('3.00'),
            effective_odds=Decimal('3.00'),
            stake=Decimal('70.00'),
            return_amount=Decimal('210.00'),
            net_result=Decimal('5.00'),
        )
        SureBetEntry.objects.create(
            bet=bet,
            bookmaker='Pinnacle',
            label='Flamengo',
            odds=Decimal('2.40'),
            effective_odds=Decimal('2.40'),
            stake=Decimal('90.00'),
            return_amount=Decimal('216.00'),
            net_result=Decimal('12.00'),
        )
        return bet

    def test_resolves_home_winner_market(self):
        bet = self.make_external_bet('Palmeiras vence')

        decision = resolve_bet_from_event(bet, self.finished_event())

        self.assertEqual(decision.status, Bet.Status.WON)

    def test_resolves_under_over_market(self):
        bet = self.make_external_bet('Over 2.5 gols')

        decision = resolve_bet_from_event(bet, self.finished_event())

        self.assertEqual(decision.status, Bet.Status.WON)

    def test_keeps_combined_market_open(self):
        bet = self.make_external_bet('Palmeiras vence e over 2.5 gols')

        decision = resolve_bet_from_event(bet, self.finished_event())

        self.assertIsNone(decision)

    def test_keeps_total_market_combined_with_other_market_open(self):
        bet = self.make_external_bet('Over 2.5 gols e ambas marcam')

        decision = resolve_bet_from_event(bet, self.finished_event())

        self.assertIsNone(decision)

    def test_apply_settlement_records_profit(self):
        bet = self.make_external_bet('Flamengo vence')
        decision = resolve_bet_from_event(bet, self.finished_event())

        apply_settlement(bet, decision)
        bet.refresh_from_db()

        self.assertEqual(bet.status, Bet.Status.LOST)
        self.assertEqual(bet.actual_net_result, Decimal('-100.00'))

    def test_resolves_surebet_winner_from_match_odds(self):
        bet = self.make_external_surebet()

        decision, winner = resolve_surebet_from_event(bet, self.finished_event())

        self.assertEqual(decision.status, Bet.Status.WON)
        self.assertEqual(winner.label, 'Palmeiras')

    def test_apply_surebet_settlement_marks_winning_entry(self):
        bet = self.make_external_surebet()
        decision, winner = resolve_surebet_from_event(bet, self.finished_event())

        apply_surebet_settlement(bet, decision, winner)
        bet.refresh_from_db()

        self.assertEqual(bet.status, Bet.Status.WON)
        self.assertEqual(bet.actual_net_result, Decimal('10.00'))
        self.assertTrue(bet.surebet_entries.get(label='Palmeiras').is_winner)

    def test_keeps_surebet_open_when_entry_market_is_not_supported(self):
        bet = self.make_external_surebet()
        bet.surebet_entries.filter(label='Empate').update(label='Ambas marcam')

        result = resolve_surebet_from_event(bet, self.finished_event())

        self.assertIsNone(result)

    def test_resolves_surebet_winner_from_goal_total(self):
        bet = self.make_external_surebet()
        bet.surebet_entries.all().delete()
        SureBetEntry.objects.create(
            bet=bet,
            bookmaker='Bet365',
            label='Over 2.5 gols',
            odds=Decimal('2.00'),
            effective_odds=Decimal('2.00'),
            stake=Decimal('100.00'),
            return_amount=Decimal('200.00'),
            net_result=Decimal('15.00'),
        )
        SureBetEntry.objects.create(
            bet=bet,
            bookmaker='Pinnacle',
            label='Under 2.5 gols',
            odds=Decimal('2.00'),
            effective_odds=Decimal('2.00'),
            stake=Decimal('100.00'),
            return_amount=Decimal('200.00'),
            net_result=Decimal('-5.00'),
        )

        decision, winner = resolve_surebet_from_event(bet, self.finished_event())

        self.assertEqual(decision.status, Bet.Status.WON)
        self.assertEqual(winner.label, 'Over 2.5 gols')


class ProtectionBalanceMovementTests(TestCase):
    def test_edit_surebet_can_change_winning_entry(self):
        user = User.objects.create_user(username='owner', password='StrongPass123!')
        entity = Entity.objects.create(owner=user, name='Operacao')
        bankroll = Bankroll.objects.create(
            owner=user,
            entity=entity,
            name='Conta principal',
            bookmaker='Bet365',
            initial_balance=Decimal('1000.00'),
        )
        second_bankroll = Bankroll.objects.create(
            owner=user,
            entity=entity,
            name='Conta Pinnacle',
            bookmaker='Pinnacle',
            initial_balance=Decimal('1000.00'),
        )
        bet = Bet.objects.create(
            bankroll=bankroll,
            game='Palmeiras x Flamengo',
            market='Proteção: Palmeiras / Flamengo',
            strategy='Surebet',
            odds=Decimal('2.00'),
            stake=Decimal('100.00'),
            status=Bet.Status.OPEN,
        )
        first_entry = SureBetEntry.objects.create(
            bet=bet,
            bankroll=bankroll,
            bookmaker='Bet365',
            label='Palmeiras',
            odds=Decimal('2.00'),
            effective_odds=Decimal('2.00'),
            stake=Decimal('100.00'),
            return_amount=Decimal('200.00'),
            net_result=Decimal('10.00'),
            is_winner=True,
        )
        second_entry = SureBetEntry.objects.create(
            bet=bet,
            bankroll=second_bankroll,
            bookmaker='Pinnacle',
            label='Flamengo',
            odds=Decimal('2.20'),
            effective_odds=Decimal('2.20'),
            stake=Decimal('90.00'),
            return_amount=Decimal('198.00'),
            net_result=Decimal('8.00'),
        )

        self.client.login(username='owner', password='StrongPass123!')
        response = self.client.get(reverse('dashboard:edit_bet', args=[bet.pk]))
        self.assertContains(response, 'Casa vencedora')
        self.assertNotContains(response, 'name="status"')

        response = self.client.post(
            reverse('dashboard:edit_bet', args=[bet.pk]),
            {
                'surebet_entity': str(entity.pk),
                'surebet_sport': 'Futebol',
                'surebet_game': 'Palmeiras x Flamengo',
                'surebet_entry_count': '2',
                'surebet_bankroll_1': str(bankroll.pk),
                'surebet_bookmaker_1': 'Bet365',
                'surebet_outcome_1': 'Palmeiras',
                'surebet_mode_1': 'back',
                'surebet_stake_1': '100.00',
                'surebet_odd_1': '2.00',
                'surebet_commission_1': '0',
                'surebet_cashback_1': '0',
                'surebet_boost_1': '0',
                'surebet_net_1': '10.00',
                'surebet_bankroll_2': str(second_bankroll.pk),
                'surebet_bookmaker_2': 'Pinnacle',
                'surebet_outcome_2': 'Flamengo',
                'surebet_mode_2': 'back',
                'surebet_stake_2': '90.00',
                'surebet_odd_2': '2.20',
                'surebet_commission_2': '0',
                'surebet_cashback_2': '0',
                'surebet_boost_2': '0',
                'surebet_net_2': '8.00',
                'winner_entry': str(second_entry.pk),
                'surebet_general_notes': '',
            },
        )

        bet.refresh_from_db()
        first_entry = bet.surebet_entries.get(label='Palmeiras')
        second_entry = bet.surebet_entries.get(label='Flamengo')
        self.assertEqual(response.status_code, 302)
        self.assertFalse(first_entry.is_winner)
        self.assertTrue(second_entry.is_winner)
        self.assertEqual(bet.status, Bet.Status.WON)
        self.assertEqual(bet.actual_net_result, Decimal('8.00'))
        self.assertEqual(bet.exact_score, 'Conta Pinnacle - Flamengo')

    def test_surebet_uses_registered_bankrolls_and_moves_each_balance(self):
        user = User.objects.create_user(username='owner', password='StrongPass123!')
        entity = Entity.objects.create(owner=user, name='Operacao')
        back_bankroll = Bankroll.objects.create(
            owner=user,
            entity=entity,
            name='Conta Bet365',
            bookmaker='Bet365',
            initial_balance=Decimal('1000.00'),
        )
        lay_bankroll = Bankroll.objects.create(
            owner=user,
            entity=entity,
            name='Conta Betfair',
            bookmaker='Betfair',
            initial_balance=Decimal('1000.00'),
        )

        self.client.login(username='owner', password='StrongPass123!')
        response = self.client.post(
            reverse('dashboard:index'),
            {
                'form_type': 'surebet',
                'surebet_entity': str(entity.pk),
                'surebet_sport': 'Futebol',
                'surebet_game': 'Palmeiras x Flamengo',
                'surebet_entry_count': '2',
                'surebet_bankroll_1': str(back_bankroll.pk),
                'surebet_outcome_1': 'Palmeiras',
                'surebet_mode_1': 'back',
                'surebet_stake_1': '40',
                'surebet_odd_1': '6.20',
                'surebet_commission_1': '0',
                'surebet_cashback_1': '0',
                'surebet_boost_1': '0',
                'surebet_bankroll_2': str(lay_bankroll.pk),
                'surebet_outcome_2': 'Flamengo',
                'surebet_mode_2': 'lay',
                'surebet_stake_2': '35.43',
                'surebet_odd_2': '7',
                'surebet_commission_2': '0',
                'surebet_cashback_2': '0',
                'surebet_boost_2': '0',
            },
        )

        self.assertEqual(response.status_code, 302)
        bet = Bet.objects.get(strategy='Surebet')
        winner = bet.surebet_entries.get(label='Palmeiras')
        loser = bet.surebet_entries.get(label='Flamengo')
        self.assertEqual(winner.bankroll, back_bankroll)
        self.assertEqual(loser.bankroll, lay_bankroll)
        self.assertEqual(loser.mode, SureBetEntry.Mode.LAY)
        self.assertEqual(loser.liability, Decimal('212.58'))

        response = self.client.post(
            reverse('dashboard:settle_surebet', args=[bet.pk]),
            {'winner_entry': str(winner.pk)},
        )

        bet.refresh_from_db()
        back_bankroll.refresh_from_db()
        lay_bankroll.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(bet.actual_net_result, Decimal('-4.58'))
        self.assertEqual(back_bankroll.current_balance, Decimal('1208.00'))
        self.assertEqual(lay_bankroll.current_balance, Decimal('787.42'))
        self.assertEqual(bet.bankroll_transactions.count(), 2)


class AuthenticationTests(TestCase):
    def test_dashboard_requires_login(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_dashboard_shows_password_change_link(self):
        User.objects.create_user(username='owner', password='StrongPass123!')
        self.client.login(username='owner', password='StrongPass123!')

        response = self.client.get('/')

        self.assertContains(response, reverse('dashboard:password_change'))
        self.assertContains(response, 'Trocar senha')

    def test_authenticated_user_can_change_password(self):
        user = User.objects.create_user(username='owner', password='StrongPass123!')
        self.client.login(username='owner', password='StrongPass123!')

        response = self.client.post(
            reverse('dashboard:password_change'),
            {
                'old_password': 'StrongPass123!',
                'new_password1': 'NewStrongPass123!',
                'new_password2': 'NewStrongPass123!',
            },
        )

        user.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard:password_change_done'))
        self.assertTrue(user.check_password('NewStrongPass123!'))
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_signup_logs_user_in_without_creating_default_bankroll(self):
        response = self.client.post(
            '/cadastro/',
            {
                'username': 'newuser',
                'email': 'new@example.com',
                'password1': 'StrongPass123!',
                'password2': 'StrongPass123!',
            },
        )

        user = User.objects.get(username='newuser')
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Bankroll.objects.filter(owner=user).exists())
        self.assertFalse(Entity.objects.filter(owner=user).exists())

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_password_reset_sends_email(self):
        User.objects.create_user(
            username='newuser',
            email='new@example.com',
            password='StrongPass123!',
        )

        response = self.client.post(
            reverse('dashboard:password_reset'),
            {'email': 'new@example.com'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard:password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/recuperar-senha/', mail.outbox[0].body)

    def test_dashboard_does_not_assign_legacy_bankroll_to_new_user(self):
        legacy_bankroll = Bankroll.objects.create(
            name='Banca principal',
            initial_balance=Decimal('500.00'),
        )
        user = User.objects.create_user(username='newuser', password='StrongPass123!')

        self.client.login(username='newuser', password='StrongPass123!')
        response = self.client.get('/')
        legacy_bankroll.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(legacy_bankroll.owner)
        self.assertFalse(Bankroll.objects.filter(owner=user).exists())

    def test_cashout_records_manual_net_result(self):
        user = User.objects.create_user(username='owner', password='StrongPass123!')
        bankroll = Bankroll.objects.create(
            owner=user,
            name='Minha banca',
            initial_balance=Decimal('1000.00'),
        )
        bet = Bet.objects.create(
            bankroll=bankroll,
            game='Time A x Time B',
            market='Resultado final',
            odds=Decimal('2.00'),
            stake=Decimal('100.00'),
            status=Bet.Status.OPEN,
        )

        self.client.login(username='owner', password='StrongPass123!')
        response = self.client.post(
            reverse('dashboard:cashout_bet', args=[bet.pk]),
            {'cashout_result': '-25,50'},
        )

        bet.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f'{reverse("dashboard:index")}#bets')
        self.assertEqual(bet.status, Bet.Status.LOST)
        self.assertEqual(bet.actual_net_result, Decimal('-25.50'))
        self.assertEqual(bet.net_result, Decimal('-25.50'))
        self.assertEqual(bet.exact_score, 'Cash out')

    def test_user_only_sees_own_bankrolls(self):
        user = User.objects.create_user(username='owner', password='StrongPass123!')
        other = User.objects.create_user(username='other', password='StrongPass123!')
        Bankroll.objects.create(owner=user, name='Minha banca', initial_balance=Decimal('100.00'))
        Bankroll.objects.create(owner=other, name='Banca escondida', initial_balance=Decimal('100.00'))

        self.client.login(username='owner', password='StrongPass123!')
        response = self.client.get('/')
        content = response.content.decode()

        self.assertContains(response, 'Minha banca')
        self.assertNotIn('Banca escondida', content)

    def test_user_can_edit_own_bank_account(self):
        user = User.objects.create_user(username='owner', password='StrongPass123!')
        bank_account = BankAccount.objects.create(
            owner=user,
            name='Nubank antigo',
            bank_name='Nubank',
            account_type=BankAccount.AccountType.PAYMENT,
        )

        self.client.login(username='owner', password='StrongPass123!')
        response = self.client.get(reverse('dashboard:edit_bank_account', args=[bank_account.pk]))
        self.assertContains(response, 'Editar Nubank antigo')

        response = self.client.post(
            reverse('dashboard:edit_bank_account', args=[bank_account.pk]),
            {
                'name': 'Nubank principal',
                'bank_name': 'Nu Pagamentos',
                'initial_balance': '2500.00',
                'account_type': BankAccount.AccountType.PAYMENT,
                'agency': '0001',
                'account_number': '12345-6',
                'pix_key': 'owner@example.com',
                'notes': 'Conta principal',
            },
        )

        bank_account.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(bank_account.name, 'Nubank principal')
        self.assertEqual(bank_account.bank_name, 'Nu Pagamentos')
        self.assertEqual(bank_account.initial_balance, Decimal('2500.00'))
        self.assertEqual(bank_account.pix_key, 'owner@example.com')

    def test_bank_account_current_balance_uses_initial_balance_and_transactions(self):
        user = User.objects.create_user(username='owner', password='StrongPass123!')
        bankroll = Bankroll.objects.create(
            owner=user,
            name='Banca',
            initial_balance=Decimal('1000.00'),
        )
        bank_account = BankAccount.objects.create(
            owner=user,
            name='Conta',
            bank_name='Banco',
            initial_balance=Decimal('500.00'),
            account_type=BankAccount.AccountType.CHECKING,
        )
        BankrollTransaction.objects.create(
            bankroll=bankroll,
            bank_account=bank_account,
            kind=BankrollTransaction.Kind.DEPOSIT,
            amount=Decimal('100.00'),
        )
        BankrollTransaction.objects.create(
            bankroll=bankroll,
            bank_account=bank_account,
            kind=BankrollTransaction.Kind.WITHDRAW,
            amount=Decimal('50.00'),
        )

        self.assertEqual(bank_account.current_balance, Decimal('450.00'))

    def test_user_cannot_edit_other_user_bank_account(self):
        user = User.objects.create_user(username='owner', password='StrongPass123!')
        other = User.objects.create_user(username='other', password='StrongPass123!')
        bank_account = BankAccount.objects.create(
            owner=other,
            name='Conta escondida',
            bank_name='Banco X',
            account_type=BankAccount.AccountType.CHECKING,
        )

        self.client.login(username='owner', password='StrongPass123!')
        response = self.client.get(reverse('dashboard:edit_bank_account', args=[bank_account.pk]))

        self.assertEqual(response.status_code, 404)

    def test_surebet_is_linked_to_entity_without_bankroll(self):
        user = User.objects.create_user(username='owner', password='StrongPass123!')
        entity = Entity.objects.create(owner=user, name='Operacao A')
        bankroll_1 = Bankroll.objects.create(
            owner=user,
            entity=entity,
            name='Banca Casa 1',
            bookmaker='Casa 1',
            initial_balance=Decimal('1000.00'),
        )
        bankroll_2 = Bankroll.objects.create(
            owner=user,
            entity=entity,
            name='Banca Casa 2',
            bookmaker='Casa 2',
            initial_balance=Decimal('1000.00'),
        )

        self.client.login(username='owner', password='StrongPass123!')
        response = self.client.post(
            '/',
            {
                'form_type': 'surebet',
                'surebet_entity': str(entity.id),
                'surebet_sport': 'Futebol',
                'surebet_competition': 'Serie A',
                'surebet_game': 'Time A x Time B',
                'surebet_entry_count': '2',
                'surebet_bankroll_1': str(bankroll_1.pk),
                'surebet_outcome_1': 'Time A',
                'surebet_odd_1': '2.10',
                'surebet_stake_1': '100.00',
                'surebet_commission_1': '0',
                'surebet_cashback_1': '0',
                'surebet_boost_1': '0',
                'surebet_freebet_enabled_1': '0',
                'surebet_bankroll_2': str(bankroll_2.pk),
                'surebet_outcome_2': 'Time B',
                'surebet_odd_2': '2.20',
                'surebet_stake_2': '95.45',
                'surebet_commission_2': '0',
                'surebet_cashback_2': '0',
                'surebet_boost_2': '0',
                'surebet_freebet_enabled_2': '0',
            },
        )

        bet = Bet.objects.get(strategy='Surebet')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(bet.entity, entity)
        self.assertIsNone(bet.bankroll)

    def test_surebet_back_lay_uses_shared_exposure_for_net_results(self):
        user = User.objects.create_user(username='owner', password='StrongPass123!')
        entity = Entity.objects.create(owner=user, name='Operacao A')
        back_bankroll = Bankroll.objects.create(
            owner=user,
            entity=entity,
            name='Banca Back',
            bookmaker='Casa Back',
            initial_balance=Decimal('1000.00'),
        )
        lay_bankroll = Bankroll.objects.create(
            owner=user,
            entity=entity,
            name='Banca Exchange',
            bookmaker='Exchange',
            initial_balance=Decimal('1000.00'),
        )

        self.client.login(username='owner', password='StrongPass123!')
        response = self.client.post(
            '/',
            {
                'form_type': 'surebet',
                'surebet_entity': str(entity.id),
                'surebet_sport': 'Futebol',
                'surebet_competition': 'Serie A',
                'surebet_game': 'Palmeiras x Flamengo',
                'surebet_entry_count': '2',
                'surebet_bankroll_1': str(back_bankroll.pk),
                'surebet_outcome_1': 'Palmeiras',
                'surebet_mode_1': 'back',
                'surebet_odd_1': '6.20',
                'surebet_stake_1': '40.00',
                'surebet_commission_1': '0',
                'surebet_cashback_1': '0',
                'surebet_boost_1': '0',
                'surebet_freebet_enabled_1': '0',
                'surebet_bankroll_2': str(lay_bankroll.pk),
                'surebet_outcome_2': 'Lay Palmeiras',
                'surebet_mode_2': 'lay',
                'surebet_odd_2': '7.00',
                'surebet_stake_2': '35.43',
                'surebet_commission_2': '0',
                'surebet_cashback_2': '0',
                'surebet_boost_2': '0',
                'surebet_freebet_enabled_2': '0',
            },
        )

        bet = Bet.objects.get(strategy='Surebet')
        back_entry = bet.surebet_entries.get(bookmaker='Casa Back')
        lay_entry = bet.surebet_entries.get(bookmaker='Exchange')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(bet.stake, Decimal('252.58'))
        self.assertEqual(back_entry.net_result, Decimal('-4.58'))
        self.assertEqual(lay_entry.net_result, Decimal('-4.57'))

    def test_freebet_extraction_marks_freebet_used(self):
        user = User.objects.create_user(username='owner', password='StrongPass123!')
        entity = Entity.objects.create(owner=user, name='Operacao A')
        promo_bankroll = Bankroll.objects.create(
            owner=user,
            entity=entity,
            name='Banca Promo',
            bookmaker='Casa Promo',
            initial_balance=Decimal('1000.00'),
        )
        protection_bankroll = Bankroll.objects.create(
            owner=user,
            entity=entity,
            name='Banca Protecao',
            bookmaker='Casa Protecao',
            initial_balance=Decimal('1000.00'),
        )
        source_bet = Bet.objects.create(
            bankroll=None,
            entity=entity,
            sport='Futebol',
            competition='Serie A',
            game='Origem x Teste',
            market='Promocao',
            strategy='Surebet',
            odds=Decimal('2.00'),
            stake=Decimal('100.00'),
        )
        freebet = FreeBet.objects.create(
            source_bet=source_bet,
            bookmaker='Casa Promo',
            amount=Decimal('50.00'),
        )

        self.client.login(username='owner', password='StrongPass123!')
        response = self.client.post(
            '/',
            {
                'form_type': 'freebet_extract',
                'freebet_source': str(freebet.id),
                'freebet_sport': 'Futebol',
                'freebet_competition': 'Serie A',
                'freebet_game': 'Time A x Time B',
                'freebet_entry_count': '2',
                'freebet_bankroll_1': str(promo_bankroll.pk),
                'freebet_outcome_1': 'Time A',
                'freebet_odd_1': '3.00',
                'freebet_commission_1': '0',
                'freebet_cashback_1': '0',
                'freebet_boost_1': '0',
                'freebet_freebet_enabled_1': '0',
                'freebet_bankroll_2': str(protection_bankroll.pk),
                'freebet_outcome_2': 'Time B',
                'freebet_odd_2': '2.00',
                'freebet_commission_2': '0',
                'freebet_cashback_2': '0',
                'freebet_boost_2': '0',
                'freebet_freebet_enabled_2': '0',
            },
        )

        bet = Bet.objects.get(strategy__contains='freebet', game='Time A x Time B')
        freebet.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(freebet.is_used)
        self.assertEqual(bet.entity, entity)
        self.assertEqual(bet.stake, Decimal('50.00'))
        self.assertEqual(bet.surebet_entries.count(), 2)

    def test_surebet_generates_freebet_when_configured_entry_loses(self):
        user = User.objects.create_user(username='owner', password='StrongPass123!')
        entity = Entity.objects.create(owner=user, name='Operacao A')
        bet = Bet.objects.create(
            bankroll=None,
            entity=entity,
            sport='Futebol',
            competition='Serie A',
            game='Time A x Time B',
            market='Surebet: Time A / Time B',
            strategy='Surebet',
            odds=Decimal('2.00'),
            stake=Decimal('100.00'),
        )
        losing_entry = SureBetEntry.objects.create(
            bet=bet,
            bookmaker='Casa Promo',
            label='Time A',
            odds=Decimal('2.00'),
            effective_odds=Decimal('2.00'),
            stake=Decimal('50.00'),
            commission=Decimal('0.00'),
            cashback=Decimal('0.00'),
            boost=Decimal('0.00'),
            return_amount=Decimal('100.00'),
            cashback_return=Decimal('0.00'),
            net_result=Decimal('-10.00'),
            freebet_enabled=True,
            freebet_amount=Decimal('25.00'),
            freebet_trigger=SureBetEntry.FreeBetTrigger.LOST,
        )
        winning_entry = SureBetEntry.objects.create(
            bet=bet,
            bookmaker='Casa Vencedora',
            label='Time B',
            odds=Decimal('2.00'),
            effective_odds=Decimal('2.00'),
            stake=Decimal('50.00'),
            commission=Decimal('0.00'),
            cashback=Decimal('0.00'),
            boost=Decimal('0.00'),
            return_amount=Decimal('100.00'),
            cashback_return=Decimal('0.00'),
            net_result=Decimal('8.00'),
        )

        self.client.login(username='owner', password='StrongPass123!')
        response = self.client.post(
            reverse('dashboard:settle_surebet', args=[bet.pk]),
            {'winner_entry': str(winning_entry.pk)},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            FreeBet.objects.filter(
                source_bet=bet,
                bookmaker=losing_entry.bookmaker,
                amount=Decimal('25.00'),
            ).exists()
        )

    @patch.dict('os.environ', {'THE_ODDS_API_KEY': 'test-key'})
    @patch('dashboard.views.OddsApiClient.events')
    def test_event_autocomplete_returns_external_games(self, mocked_events):
        mocked_events.return_value = [
            {
                'id': 'event-1',
                'home_team': 'Palmeiras',
                'away_team': 'Flamengo',
                'sport_title': 'Brasileirao',
                'commence_time': '2026-05-22T22:30:00Z',
            }
        ]
        user = User.objects.create_user(username='owner', password='StrongPass123!')

        self.client.login(username='owner', password='StrongPass123!')
        response = self.client.get(
            reverse('dashboard:event_autocomplete'),
            {'q': 'Palmeiras', 'sport': 'Futebol', 'competition': 'Brasileirao'},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['results'][0]['game'], 'Palmeiras x Flamengo')
        self.assertEqual(payload['results'][0]['competition'], 'Brasileirao')
        self.assertTrue(payload['results'][0]['event_date'])

    @patch.dict('os.environ', {'THE_ODDS_API_KEY': 'test-key'})
    @patch('dashboard.views.OddsApiClient.event_odds')
    def test_event_odds_returns_bookmakers_for_selected_game(self, mocked_event_odds):
        mocked_event_odds.return_value = {
            'id': 'event-bahia-coritiba',
            'home_team': 'Bahia',
            'away_team': 'Coritiba',
            'sport_title': 'Brasileirao',
            'commence_time': '2026-05-22T22:30:00Z',
            'bookmakers': [
                {
                    'key': 'bet365',
                    'title': 'Bet365',
                    'markets': [
                        {
                            'key': 'h2h',
                            'outcomes': [
                                {'name': 'Bahia', 'price': 1.03},
                                {'name': 'Draw', 'price': 17.0},
                                {'name': 'Coritiba', 'price': 51.0},
                            ],
                        }
                    ],
                }
            ],
        }
        user = User.objects.create_user(username='owner', password='StrongPass123!')

        self.client.login(username='owner', password='StrongPass123!')
        response = self.client.get(
            reverse('dashboard:event_odds'),
            {
                'event_id': 'event-bahia-coritiba',
                'sport_key': 'soccer_brazil_campeonato',
                'event_odds-sport': 'soccer_brazil_campeonato',
                'event_odds-regions': 'eu',
                'event_odds-bookmakers': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['event'], 'Bahia x Coritiba')
        self.assertEqual(payload['outcome_names'], ['Bahia', 'Draw', 'Coritiba'])
        self.assertEqual(payload['bookmakers'][0]['title'], 'Bet365')
        self.assertEqual(payload['bookmakers'][0]['outcomes']['Coritiba'], 51.0)

    @patch.dict('os.environ', {'THE_ODDS_API_KEY': 'test-key'})
    @patch('dashboard.views.OddsApiClient.event_odds')
    def test_event_odds_accepts_sport_key_when_select_value_is_stale(self, mocked_event_odds):
        mocked_event_odds.return_value = {
            'id': 'event-1',
            'home_team': 'Atletico Paranaense',
            'away_team': 'Mirassol',
            'sport_title': 'Brasileirao',
            'bookmakers': [],
        }
        user = User.objects.create_user(username='owner', password='StrongPass123!')

        self.client.login(username='owner', password='StrongPass123!')
        response = self.client.get(
            reverse('dashboard:event_odds'),
            {
                'event_id': 'event-1',
                'sport_key': 'soccer_brazil_campeonato',
                'event_odds-sport': 'Futebol',
                'event_odds-regions': 'eu',
                'event_odds-bookmakers': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        mocked_event_odds.assert_called_once()

    @patch.dict('os.environ', {'THE_ODDS_API_KEY': 'test-key'})
    @patch('dashboard.views.OddsApiClient.event_odds')
    def test_event_odds_filters_region_results_by_user_regulated_aliases(self, mocked_event_odds):
        mocked_event_odds.return_value = {
            'id': 'event-aliases',
            'home_team': 'Bahia',
            'away_team': 'Coritiba',
            'sport_title': 'Brasileirao',
            'bookmakers': [
                {
                    'key': 'bet365',
                    'title': 'Bet365',
                    'markets': [{'key': 'h2h', 'outcomes': [{'name': 'Bahia', 'price': 1.5}]}],
                },
                {
                    'key': 'unknown_book',
                    'title': 'Unknown Book',
                    'markets': [{'key': 'h2h', 'outcomes': [{'name': 'Bahia', 'price': 1.7}]}],
                },
                {
                    'key': 'betano',
                    'title': 'Betano',
                    'markets': [{'key': 'h2h', 'outcomes': [{'name': 'Bahia', 'price': 1.6}]}],
                },
            ],
        }
        user = User.objects.create_user(username='owner', password='StrongPass123!')
        bet365 = RegulatedBookmaker.objects.create(
            owner=user,
            company_name='Bet365 Brasil',
            brand='Bet365',
            domain='bet365.bet.br',
        )
        betano = RegulatedBookmaker.objects.create(
            owner=user,
            company_name='Betano Brasil',
            brand='Betano',
            domain='betano.bet.br',
        )
        BookmakerAlias.objects.create(
            bookmaker=bet365,
            provider='the_odds_api',
            alias='Bet365',
            provider_key='bet365',
        )
        BookmakerAlias.objects.create(
            bookmaker=betano,
            provider='the_odds_api',
            alias='Betano',
            provider_key='betano',
        )

        self.client.login(username='owner', password='StrongPass123!')
        response = self.client.get(
            reverse('dashboard:event_odds'),
            {
                'event_id': 'event-aliases',
                'sport_key': 'soccer_brazil_campeonato',
                'event_odds-sport': 'soccer_brazil_campeonato',
                'event_odds-regions': 'eu',
                'event_odds-bookmakers': '',
                'event_odds-brazil_regulated_only': 'on',
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['uses_regulated_aliases'])
        self.assertEqual(payload['bookmaker_filter'], '')
        self.assertEqual(payload['regions_used'], 'eu,uk,us,au')
        self.assertEqual([bookmaker['title'] for bookmaker in payload['bookmakers']], ['Bet365', 'Betano'])
        mocked_event_odds.assert_called_once()
        self.assertEqual(mocked_event_odds.call_args.kwargs['bookmakers'], '')
        self.assertEqual(mocked_event_odds.call_args.kwargs['regions'], 'eu,uk,us,au')

    @patch.dict('os.environ', {'THE_ODDS_API_KEY': 'test-key'})
    @patch('dashboard.views.OddsApiClient.event_odds')
    def test_event_odds_expands_results_when_only_one_priority_book_is_available(self, mocked_event_odds):
        mocked_event_odds.return_value = {
            'id': 'event-priority',
            'home_team': 'Bahia',
            'away_team': 'Botafogo',
            'sport_title': 'Brasileirao',
            'bookmakers': [
                {
                    'key': 'betclic',
                    'title': 'Betclic',
                    'markets': [{'key': 'h2h', 'outcomes': [{'name': 'Bahia', 'price': 1.8}]}],
                },
                {
                    'key': 'betano',
                    'title': 'Betano',
                    'markets': [{'key': 'h2h', 'outcomes': [{'name': 'Bahia', 'price': 1.7}]}],
                },
            ],
        }
        user = User.objects.create_user(username='owner', password='StrongPass123!')

        self.client.login(username='owner', password='StrongPass123!')
        response = self.client.get(
            reverse('dashboard:event_odds'),
            {
                'event_id': 'event-priority',
                'sport_key': 'soccer_brazil_campeonato',
                'event_odds-sport': 'soccer_brazil_campeonato',
                'event_odds-regions': 'eu',
                'event_odds-bookmakers': '',
                'event_odds-brazil_regulated_only': 'on',
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual([bookmaker['title'] for bookmaker in payload['bookmakers']], ['Betclic', 'Betano'])
        self.assertTrue(payload['filter_note'])


@override_settings(
    MERCADO_PAGO_ACCESS_TOKEN='TEST-access-token',
    MERCADO_PAGO_ENVIRONMENT='sandbox',
    MERCADO_PAGO_WEBHOOK_SECRET='test-webhook-secret',
)
class MercadoPagoCheckoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='subscriber',
            email='subscriber@example.com',
            password='StrongPass123!',
        )
        self.client.force_login(self.user)

    def signed_webhook_headers(self, provider_payment_id, request_id='request-test-123', timestamp='1704908010'):
        manifest = f'id:{provider_payment_id.lower()};request-id:{request_id};ts:{timestamp};'
        signature = hmac.new(
            b'test-webhook-secret',
            manifest.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()
        return {
            'HTTP_X_SIGNATURE': f'ts={timestamp},v1={signature}',
            'HTTP_X_REQUEST_ID': request_id,
        }

    @patch('dashboard.views.mercado_pago_request')
    def test_monthly_checkout_creates_preference_and_redirects_to_sandbox(self, mocked_request):
        mocked_request.return_value = {
            'id': 'preference-test-1',
            'sandbox_init_point': 'https://sandbox.mercadopago.com.br/checkout/test-1',
        }

        response = self.client.post(reverse('dashboard:subscription_checkout', args=['monthly']))

        self.assertRedirects(
            response,
            'https://sandbox.mercadopago.com.br/checkout/test-1',
            fetch_redirect_response=False,
        )
        payment = Payment.objects.get(user=self.user)
        self.assertEqual(payment.plan, Payment.Plan.MONTHLY)
        self.assertEqual(payment.amount, Decimal('20.00'))
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertEqual(payment.provider_preference_id, 'preference-test-1')
        self.assertEqual(payment.checkout_url, 'https://sandbox.mercadopago.com.br/checkout/test-1')

        method, path, payload = mocked_request.call_args.args
        self.assertEqual((method, path), ('POST', '/checkout/preferences'))
        self.assertEqual(payload['external_reference'], str(payment.pk))
        self.assertEqual(payload['metadata']['plan'], Payment.Plan.MONTHLY)
        self.assertEqual(payload['items'][0]['unit_price'], 20.0)

    @patch('dashboard.views.mercado_pago_request')
    def test_approved_webhook_activates_access_for_payment_duration(self, mocked_request):
        payment = Payment.build_for_plan(self.user, Payment.Plan.QUARTERLY)
        mocked_request.return_value = {
            'id': 'mp-payment-123',
            'status': 'approved',
            'external_reference': str(payment.pk),
        }

        response = self.client.post(
            f"{reverse('dashboard:mercado_pago_webhook')}?data.id=mp-payment-123",
            data=json.dumps({'type': 'payment', 'data': {'id': 'mp-payment-123'}}),
            content_type='application/json',
            **self.signed_webhook_headers('mp-payment-123'),
        )

        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        access = UserAccess.objects.get(user=self.user)
        self.assertEqual(payment.status, Payment.Status.APPROVED)
        self.assertEqual(payment.provider_payment_id, 'mp-payment-123')
        self.assertEqual(access.status, UserAccess.Status.ACTIVE)
        self.assertGreaterEqual(access.subscription_ends_at, timezone.now() + timedelta(days=89))

        expiration_before_retry = access.subscription_ends_at
        retry_response = self.client.post(
            f"{reverse('dashboard:mercado_pago_webhook')}?data.id=mp-payment-123",
            data=json.dumps({'type': 'payment', 'data': {'id': 'mp-payment-123'}}),
            content_type='application/json',
            **self.signed_webhook_headers('mp-payment-123'),
        )
        self.assertEqual(retry_response.status_code, 200)
        access.refresh_from_db()
        self.assertEqual(access.subscription_ends_at, expiration_before_retry)

    @patch('dashboard.views.mercado_pago_request')
    def test_webhook_with_invalid_signature_does_not_change_payment(self, mocked_request):
        payment = Payment.build_for_plan(self.user, Payment.Plan.MONTHLY)

        response = self.client.post(
            f"{reverse('dashboard:mercado_pago_webhook')}?data.id=mp-payment-invalid",
            data=json.dumps({'type': 'payment', 'data': {'id': 'mp-payment-invalid'}}),
            content_type='application/json',
            HTTP_X_SIGNATURE='ts=1704908010,v1=invalid',
            HTTP_X_REQUEST_ID='request-test-123',
        )

        self.assertEqual(response.status_code, 401)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertFalse(UserAccess.objects.filter(user=self.user).exists())
        mocked_request.assert_not_called()

    @patch('dashboard.views.mercado_pago_request')
    def test_signed_webhook_for_unknown_payment_is_ignored(self, mocked_request):
        mocked_request.return_value = {
            'id': 'mp-payment-unknown',
            'status': 'approved',
            'external_reference': '999999',
        }

        response = self.client.post(
            f"{reverse('dashboard:mercado_pago_webhook')}?data.id=mp-payment-unknown",
            data=json.dumps({'type': 'payment', 'data': {'id': 'mp-payment-unknown'}}),
            content_type='application/json',
            **self.signed_webhook_headers('mp-payment-unknown'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ignored'])
        self.assertFalse(UserAccess.objects.filter(user=self.user).exists())

    @override_settings(MERCADO_PAGO_WEBHOOK_SECRET='')
    def test_webhook_is_unavailable_without_secret(self):
        response = self.client.post(reverse('dashboard:mercado_pago_webhook'))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['reason'], 'secret_not_configured')


class SalesSubscriptionCtaTests(TestCase):
    def test_expired_user_is_sent_to_subscription_from_sales_ctas(self):
        user = User.objects.create_user(username='expired-user', password='StrongPass123!')
        access = UserAccess.create_trial_for(user)
        access.status = UserAccess.Status.EXPIRED
        access.trial_ends_at = timezone.now() - timedelta(days=1)
        access.save(update_fields=['status', 'trial_ends_at', 'updated_at'])
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard:sales'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('dashboard:subscription'), count=5)
        self.assertNotContains(response, 'href="/cadastro/">Começar teste grátis</a>')


@override_settings(FREEBETAR_SITE_URL='https://freebetar.example')
class SubscriptionReminderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='renewal-user',
            email='renewal@example.com',
            password='StrongPass123!',
        )
        self.access = UserAccess.create_trial_for(self.user)
        self.access.status = UserAccess.Status.ACTIVE
        self.access.subscription_ends_at = timezone.now() + timedelta(days=7)
        self.access.save(update_fields=['status', 'subscription_ends_at', 'updated_at'])

    def test_command_sends_one_reminder_and_does_not_repeat_it(self):
        call_command('send_subscription_reminders')

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('vence em 7 dia(s)', mail.outbox[0].subject)
        self.assertIn('https://freebetar.example/assinatura/', mail.outbox[0].body)
        self.assertTrue(SubscriptionReminder.objects.filter(access=self.access, days_before=7).exists())

        call_command('send_subscription_reminders')
        self.assertEqual(len(mail.outbox), 1)

    def test_dashboard_shows_renewal_notice_once_per_day(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('dashboard:index'))

        self.assertContains(response, 'Sua assinatura vence em 7 dia(s).')
        response = self.client.get(reverse('dashboard:index'))
        self.assertNotContains(response, 'Sua assinatura vence em 7 dia(s).')


class OnboardingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='onboarding-user', password='StrongPass123!')
        self.client.force_login(self.user)

    def test_new_user_sees_financial_setup_steps_and_surebet_guidance(self):
        response = self.client.get(reverse('dashboard:index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Monte sua operação no Freebetar')
        self.assertContains(response, 'data-onboarding-action="bank-account"')
        self.assertContains(response, 'Na aposta 2, preencha apenas a casa e a odd')
        self.assertContains(response, 'name="surebet_stake_2"', count=1)
        self.assertContains(response, 'name="surebet_stake_2" value="" class="surebet-stake calculated-stake" step="0.01" min="0.01" placeholder="Calculado" readonly')
        self.assertContains(response, 'Como acompanhar suas apostas')

    def test_onboarding_hides_after_financial_setup_and_first_bet(self):
        entity = Entity.objects.create(owner=self.user, name='Operação própria')
        bankroll = Bankroll.objects.create(
            owner=self.user,
            entity=entity,
            name='Operação própria - Bet365',
            bookmaker='Bet365',
            initial_balance=Decimal('100.00'),
        )
        BankAccount.objects.create(owner=self.user, name='Nubank', bank_name='Nubank')
        Bet.objects.create(
            entity=entity,
            bankroll=bankroll,
            game='Palmeiras x Bahia',
            market='Casa vence',
            odds=Decimal('1.80'),
            stake=Decimal('20.00'),
        )

        response = self.client.get(reverse('dashboard:index'))

        self.assertNotContains(response, 'Monte sua operação no Freebetar')
        self.assertContains(response, 'Sua primeira aposta já está registrada')
        self.assertContains(response, 'data-onboarding-action="history"')
        self.assertContains(response, 'placeholder="Lucro/prejuízo"')
