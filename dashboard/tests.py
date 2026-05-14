from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User

from django.test import TestCase
from django.utils import timezone

from .analytics import build_analytics
from .analytics import build_month_calendar
from .analytics import max_drawdown
from .automation import import_bets_from_csv
from .automation import import_bets_from_text
from .forms import BankrollForm
from .forms import BankrollTransactionForm
from .forms import BetForm
from .forms import TransferForm
from .models import Bankroll
from .models import BankrollTransaction
from .models import Bet
from .models import MonthlyGoal
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
        form = BankrollForm(
            data={
                'name': 'Exchange',
                'bookmaker': 'Betfair',
                'initial_balance': '500.00',
                'unit_percentage': '1.00',
                'max_stake_percentage': '10.00',
                'daily_stop_loss_percentage': '5.00',
                'weekly_stop_loss_percentage': '10.00',
                'monthly_stop_loss_percentage': '20.00',
                'daily_stop_win_percentage': '8.00',
            }
        )

        self.assertTrue(form.is_valid())


class RiskManagementTests(TestCase):
    def test_stake_cannot_exceed_max_stake_amount(self):
        bankroll = Bankroll.objects.create(
            name='Banca principal',
            initial_balance=Decimal('1000.00'),
            max_stake_percentage=Decimal('5.00'),
        )

        form = BetForm(
            data={
                'bankroll': bankroll.id,
                'sport': 'Futebol',
                'game': 'Teste x Exemplo',
                'market': 'Vencedor',
                'entry_type': Bet.EntryType.PRE_MATCH,
                'odds': '2.00',
                'stake': '80.00',
                'exchange_commission': '0',
                'status': Bet.Status.OPEN,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn('stake', form.errors)

    def test_suggested_unit_uses_configured_percentage(self):
        bankroll = Bankroll.objects.create(
            name='Banca principal',
            initial_balance=Decimal('1000.00'),
            unit_percentage=Decimal('2.00'),
        )

        self.assertEqual(bankroll.suggested_unit, Decimal('20.00'))
        self.assertEqual(bankroll.max_stake_amount, Decimal('100.00'))

    def test_unit_percentage_cannot_exceed_max_stake_percentage(self):
        form = BankrollForm(
            data={
                'name': 'Exchange',
                'bookmaker': 'Betfair',
                'initial_balance': '500.00',
                'unit_percentage': '5.00',
                'max_stake_percentage': '2.00',
                'daily_stop_loss_percentage': '5.00',
                'weekly_stop_loss_percentage': '10.00',
                'monthly_stop_loss_percentage': '20.00',
                'daily_stop_win_percentage': '8.00',
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn('unit_percentage', form.errors)


class AnalyticsTests(TestCase):
    def setUp(self):
        self.bankroll = Bankroll.objects.create(
            name='Banca principal',
            initial_balance=Decimal('1000.00'),
        )

    def test_build_analytics_returns_grouped_roi_and_streak(self):
        now = timezone.now()
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
        bankroll = Bankroll.objects.create(name='Banca principal', initial_balance=Decimal('1000.00'))
        Bet.objects.create(
            bankroll=bankroll,
            game='Time A x Time B',
            market='Over 2.5',
            odds=Decimal('2.00'),
            stake=Decimal('50.00'),
            status=Bet.Status.WON,
            created_at=timezone.now(),
        )
        goal = MonthlyGoal.objects.create(
            bankroll=bankroll,
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


class AuthenticationTests(TestCase):
    def test_dashboard_requires_login(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_signup_logs_user_in_and_creates_default_bankroll(self):
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
        self.assertTrue(Bankroll.objects.filter(owner=user, name='Banca principal').exists())

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
