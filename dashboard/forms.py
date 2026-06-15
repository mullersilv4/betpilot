from decimal import Decimal

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db.models import Q

from .models import BankAccount
from .models import Bankroll
from .models import BankrollTransaction
from .models import Bet
from .models import Entity
from .models import FreeBet
from .models import MonthlyGoal
from .models import BookmakerAlias
from .models import Promotion
from .models import PromotionPage
from .models import RegulatedBookmaker
from .models import UserPreference


class EntityForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    class Meta:
        model = Entity
        fields = ['name', 'notes']
        widgets = {
            'name': forms.TextInput(
                attrs={
                    'placeholder': 'Ex: Muller, Cliente A, Projeto X',
                    'autocomplete': 'off',
                }
            ),
            'notes': forms.TextInput(
                attrs={
                    'placeholder': 'Ex: Operação própria, parceiro, cliente...',
                    'autocomplete': 'off',
                }
            ),
        }

    def clean_name(self):
        name = self.cleaned_data['name']
        if self.user and Entity.objects.filter(owner=self.user, name__iexact=name).exists():
            raise forms.ValidationError('Você já cadastrou uma entidade com esse nome.')
        return name


class UserPreferenceForm(forms.ModelForm):
    class Meta:
        model = UserPreference
        fields = ['language', 'currency']
        widgets = {
            'language': forms.Select(),
            'currency': forms.Select(),
        }


class BankrollForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['entity'].queryset = Entity.objects.filter(owner=user)
        self.fields['entity'].empty_label = 'Selecione uma entidade'
        self.fields['entity'].required = True

    class Meta:
        model = Bankroll
        fields = [
            'entity',
            'bookmaker',
            'initial_balance',
        ]
        widgets = {
            'entity': forms.Select(),
            'bookmaker': forms.TextInput(
                attrs={
                    'placeholder': 'Ex: Betfair, Bet365, Pinnacle',
                    'autocomplete': 'off',
                }
            ),
            'initial_balance': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }

    def clean_initial_balance(self):
        initial_balance = self.cleaned_data['initial_balance']
        if initial_balance < 0:
            raise forms.ValidationError('O saldo inicial não pode ser negativo.')
        return initial_balance

    def save(self, commit=True):
        bankroll = super().save(commit=False)
        entity_name = bankroll.entity.name if bankroll.entity else 'Sem entidade'
        bookmaker = bankroll.bookmaker or 'Sem casa'
        bankroll.name = f'{entity_name} - {bookmaker}'
        if commit:
            bankroll.save()
            self.save_m2m()
        return bankroll

class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=False)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')


class BetForm(forms.ModelForm):
    freebet_source = forms.ModelChoiceField(
        label='Usar freebet',
        queryset=FreeBet.objects.none(),
        required=False,
        empty_label='Não usar freebet',
        widget=forms.Select(attrs={'data-simple-freebet-select': 'true'}),
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        show_status = kwargs.pop('show_status', True)
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['bankroll'].queryset = Bankroll.objects.filter(owner=user)
            freebet_filter = (
                Q(owner=user)
                | Q(source_bet__bankroll__owner=user)
                | Q(source_bet__entity__owner=user)
            )
            current_freebet = None
            if self.instance and self.instance.pk:
                try:
                    current_freebet = self.instance.simple_freebet
                except FreeBet.DoesNotExist:
                    current_freebet = None
            available_filter = Q(is_used=False)
            if current_freebet is not None:
                available_filter |= Q(pk=current_freebet.pk)
                self.initial['freebet_source'] = current_freebet.pk
            self.fields['freebet_source'].queryset = (
                FreeBet.objects.filter(freebet_filter)
                .filter(available_filter)
                .select_related('source_bet', 'simple_bet')
                .distinct()
            )
        self.fields['game'].required = False
        if not show_status:
            self.fields.pop('status', None)
        if self.instance and self.instance.event_date:
            self.initial['event_date'] = self.instance.event_date.strftime('%Y-%m-%d')
        self.fields['event_date'].input_formats = ['%Y-%m-%d']

    class Meta:
        model = Bet
        fields = [
            'bankroll',
            'sport',
            'competition',
            'game',
            'external_event_id',
            'external_sport_key',
            'home_team',
            'away_team',
            'market',
            'strategy',
            'event_date',
            'entry_type',
            'freebet_source',
            'odds',
            'stake',
            'exchange_commission',
            'status',
            'exact_score',
            'game_link',
            'notes',
        ]
        widgets = {
            'bankroll': forms.Select(),
            'sport': forms.TextInput(
                attrs={
                    'placeholder': 'Ex: Futebol, Basquete, Tenis',
                    'autocomplete': 'off',
                }
            ),
            'competition': forms.TextInput(
                attrs={
                    'placeholder': 'Ex: Brasileirão, NBA, ATP',
                    'autocomplete': 'off',
                }
            ),
            'game': forms.TextInput(
                attrs={
                    'placeholder': 'Ex: Palmeiras x Flamengo',
                    'autocomplete': 'off',
                }
            ),
            'external_event_id': forms.HiddenInput(),
            'external_sport_key': forms.HiddenInput(),
            'home_team': forms.HiddenInput(),
            'away_team': forms.HiddenInput(),
            'market': forms.TextInput(
                attrs={
                    'placeholder': 'Ex: Over 2.5 gols, ML, Handicap -1.5',
                    'autocomplete': 'off',
                }
            ),
            'strategy': forms.TextInput(
                attrs={
                    'placeholder': 'Ex: Escanteios HT, Tipster X, Modelo gols',
                    'autocomplete': 'off',
                }
            ),
            'event_date': forms.DateInput(attrs={'type': 'date'}),
            'entry_type': forms.Select(),
            'odds': forms.NumberInput(attrs={'step': '0.01', 'min': '1.01'}),
            'stake': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
            'exchange_commission': forms.NumberInput(
                attrs={'step': '0.01', 'min': '0', 'max': '100'}
            ),
            'status': forms.Select(),
            'exact_score': forms.TextInput(
                attrs={
                    'placeholder': 'Ex: 2x1, 0x0, 101-98',
                    'autocomplete': 'off',
                }
            ),
            'game_link': forms.URLInput(
                attrs={
                    'placeholder': 'https://...',
                    'autocomplete': 'off',
                }
            ),
            'notes': forms.Textarea(
                attrs={
                    'rows': 3,
                    'placeholder': 'Contexto da entrada, leitura do jogo, motivo da aposta...',
                }
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        bankroll = cleaned_data.get('bankroll')
        stake = cleaned_data.get('stake')
        freebet_source = cleaned_data.get('freebet_source')

        if freebet_source:
            cleaned_data['stake'] = freebet_source.amount
            stake = freebet_source.amount

        available_balance = bankroll.available_balance if bankroll else 0
        if (
            bankroll
            and self.instance.pk
            and self.instance.bankroll_id == bankroll.id
            and self.instance.status == Bet.Status.OPEN
            and not self.instance.uses_simple_freebet
        ):
            available_balance += self.instance.stake

        if bankroll and stake and not freebet_source and stake > available_balance:
            self.add_error(
                'stake',
                'O valor da aposta não pode ser maior que o saldo disponível da banca.',
            )

        return cleaned_data

    def clean_odds(self):
        odds = self.cleaned_data['odds']
        if odds <= 1:
            raise forms.ValidationError('A odd precisa ser maior que 1.00.')
        return odds

    def clean_exchange_commission(self):
        commission = self.cleaned_data['exchange_commission']
        if commission < 0 or commission > 100:
            raise forms.ValidationError('Informe uma porcentagem entre 0 e 100.')
        return commission


class BankrollTransactionForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.original_signed_amount = self.instance.signed_amount if self.instance.pk else 0
        if user is not None:
            self.fields['bankroll'].queryset = Bankroll.objects.filter(owner=user)
            self.fields['bank_account'].queryset = BankAccount.objects.filter(owner=user)
        self.fields['kind'].choices = [
            (BankrollTransaction.Kind.DEPOSIT, 'Deposito'),
            (BankrollTransaction.Kind.WITHDRAW, 'Saque'),
            (BankrollTransaction.Kind.ADJUSTMENT, 'Ajuste'),
        ]
        if self.instance.pk and self.instance.kind == BankrollTransaction.Kind.ADJUSTMENT:
            self.initial['amount'] = self.instance.bankroll.current_balance

    class Meta:
        model = BankrollTransaction
        fields = ['bankroll', 'kind', 'bank_account', 'amount', 'note']
        widgets = {
            'bankroll': forms.Select(),
            'kind': forms.Select(),
            'bank_account': forms.Select(),
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
            'note': forms.TextInput(
                attrs={
                    'placeholder': 'Ex: deposito Pix, saque parcial, ajuste manual',
                    'autocomplete': 'off',
                }
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        bankroll = cleaned_data.get('bankroll')
        kind = cleaned_data.get('kind')
        bank_account = cleaned_data.get('bank_account')
        amount = cleaned_data.get('amount')

        if (
            bankroll
            and amount
            and kind in {BankrollTransaction.Kind.WITHDRAW, BankrollTransaction.Kind.TRANSFER_OUT}
            and amount > bankroll.available_balance
        ):
            self.add_error(
                'amount',
                'O valor não pode ser maior que o saldo disponível da banca.',
            )

        return cleaned_data

    def save(self, commit=True):
        transaction = super().save(commit=False)
        if (
            transaction.kind == BankrollTransaction.Kind.ADJUSTMENT
            and transaction.bankroll_id
            and self.cleaned_data.get('amount') is not None
        ):
            target_balance = self.cleaned_data['amount']
            base_balance = transaction.bankroll.current_balance
            if transaction.pk:
                base_balance -= self.original_signed_amount
            transaction.amount = target_balance - base_balance

        if commit:
            transaction.save()
            self.save_m2m()

        return transaction


class BankAccountForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['initial_balance'].required = False

    class Meta:
        model = BankAccount
        fields = [
            'name',
            'bank_name',
            'initial_balance',
            'account_type',
            'agency',
            'account_number',
            'pix_key',
            'notes',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Ex: Nubank principal', 'autocomplete': 'off'}),
            'bank_name': forms.TextInput(attrs={'placeholder': 'Ex: Nubank, Itaú, Banco Inter', 'autocomplete': 'off'}),
            'initial_balance': forms.NumberInput(attrs={'step': '0.01'}),
            'account_type': forms.Select(),
            'agency': forms.TextInput(attrs={'placeholder': 'Opcional', 'autocomplete': 'off'}),
            'account_number': forms.TextInput(attrs={'placeholder': 'Opcional', 'autocomplete': 'off'}),
            'pix_key': forms.TextInput(attrs={'placeholder': 'CPF, email, telefone ou chave aleatória', 'autocomplete': 'off'}),
            'notes': forms.TextInput(attrs={'placeholder': 'Observação opcional', 'autocomplete': 'off'}),
        }

    def clean_initial_balance(self):
        return self.cleaned_data.get('initial_balance') or Decimal('0.00')


class TransferForm(forms.Form):
    source = forms.ModelChoiceField(
        label='banca de origem',
        queryset=Bankroll.objects.all(),
        empty_label=None,
    )
    target = forms.ModelChoiceField(
        label='banca de destino',
        queryset=Bankroll.objects.all(),
        empty_label=None,
    )
    amount = forms.DecimalField(
        label='valor',
        max_digits=12,
        decimal_places=2,
        min_value=0.01,
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user is not None:
            queryset = Bankroll.objects.filter(owner=user)
            self.fields['source'].queryset = queryset
            self.fields['target'].queryset = queryset

    def clean(self):
        cleaned_data = super().clean()
        source = cleaned_data.get('source')
        target = cleaned_data.get('target')
        amount = cleaned_data.get('amount')

        if source and target and source == target:
            raise forms.ValidationError('A origem e o destino precisam ser bancas diferentes.')

        if source and amount and amount > source.available_balance:
            self.add_error(
                'amount',
                'A transferência não pode ser maior que o saldo disponível.',
            )

        return cleaned_data


class BetFilterForm(forms.Form):
    bankroll = forms.ModelChoiceField(
        label='banca',
        queryset=Bankroll.objects.all(),
        required=False,
        empty_label='Todas',
    )
    status = forms.ChoiceField(
        label='status',
        choices=[('', 'Todos')] + list(Bet.Status.choices),
        required=False,
    )
    entry_type = forms.ChoiceField(
        label='tipo',
        choices=[('', 'Todos')] + list(Bet.EntryType.choices),
        required=False,
    )
    sport = forms.CharField(label='esporte', required=False)
    strategy = forms.CharField(label='estratégia', required=False)
    query = forms.CharField(label='busca', required=False)
    event_date = forms.DateField(
        label='data',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['bankroll'].queryset = Bankroll.objects.filter(owner=user)


class ImportTextForm(forms.Form):
    raw_text = forms.CharField(
        label='texto/CSV',
        required=False,
        widget=forms.Textarea(
            attrs={
                'rows': 5,
                'placeholder': (
                    'Uma aposta por linha: banca;jogo;mercado;odd;valor;comissão;status\n'
                    'Formato novo: banca;esporte;competição;jogo;mercado;estratégia;tipo;data;odd;valor;comissão;status\n'
                    'Ex: Banca principal;Futebol;Brasileirão;Palmeiras x Flamengo;Over 2.5;Modelo gols;pre_match;2026-05-13 21:30;1.90;100;5;open'
                ),
            }
        ),
    )
    csv_file = forms.FileField(label='arquivo CSV', required=False)

    def clean(self):
        cleaned_data = super().clean()
        raw_text = cleaned_data.get('raw_text')
        csv_file = cleaned_data.get('csv_file')

        if not raw_text and not csv_file:
            raise forms.ValidationError('Cole um texto ou envie um arquivo CSV.')

        return cleaned_data


class OddsSearchForm(forms.Form):
    SPORT_CHOICES = [
        ('soccer_epl', 'Futebol - Premier League'),
        ('soccer_brazil_campeonato', 'Futebol - Brasileirão'),
        ('soccer_uefa_champs_league', 'Futebol - Champions League'),
        ('soccer_spain_la_liga', 'Futebol - La Liga'),
        ('soccer_italy_serie_a', 'Futebol - Serie A'),
        ('soccer_germany_bundesliga', 'Futebol - Bundesliga'),
        ('soccer_france_ligue_one', 'Futebol - Ligue 1'),
        ('basketball_nba', 'Basquete - NBA'),
        ('americanfootball_nfl', 'Futebol americano - NFL'),
    ]
    REGION_CHOICES = [
        ('eu', 'Europa'),
        ('uk', 'Reino Unido'),
        ('us', 'Estados Unidos'),
        ('au', 'Australia'),
        ('eu,uk', 'Europa + Reino Unido'),
        ('eu,uk,us', 'Europa + Reino Unido + EUA'),
    ]

    sport = forms.ChoiceField(
        label='liga/esporte',
        choices=SPORT_CHOICES,
        initial='soccer_epl',
    )
    regions = forms.ChoiceField(
        label='regiões',
        choices=REGION_CHOICES,
        initial='eu',
    )
    bookmakers = forms.CharField(
        label='casas',
        required=False,
        widget=forms.TextInput(
            attrs={
                'placeholder': 'Opcional: betano,superbet,bet365,novibet',
                'autocomplete': 'off',
            }
        ),
    )
    brazil_regulated_only = forms.BooleanField(
        label='apenas casas regulamentadas no Brasil',
        required=False,
        initial=True,
    )
    stake = forms.DecimalField(
        label='investimento',
        initial=100,
        min_value=1,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '1'}),
    )
    limit = forms.IntegerField(
        label='limite',
        initial=10,
        min_value=1,
        max_value=50,
        widget=forms.NumberInput(attrs={'min': '1', 'max': '50'}),
    )


class EventOddsForm(forms.Form):
    sport = forms.ChoiceField(
        label='campeonato',
        choices=OddsSearchForm.SPORT_CHOICES,
        initial='soccer_brazil_campeonato',
        widget=forms.Select(attrs={'data-event-sport-input': ''}),
    )
    regions = forms.ChoiceField(
        label='casas por região',
        choices=OddsSearchForm.REGION_CHOICES,
        initial='eu',
    )
    bookmakers = forms.CharField(
        label='casas',
        required=False,
        widget=forms.TextInput(
            attrs={
                'placeholder': 'Opcional: betano,superbet,bet365,novibet',
                'autocomplete': 'off',
            }
        ),
    )
    brazil_regulated_only = forms.BooleanField(
        label='apenas casas regulamentadas no Brasil',
        required=False,
        initial=True,
    )


class RegulatedBookmakerForm(forms.ModelForm):
    class Meta:
        model = RegulatedBookmaker
        fields = [
            'company_name',
            'brand',
            'cnpj',
            'domain',
            'status',
            'judicial_alert',
            'alert_note',
        ]
        widgets = {
            'company_name': forms.TextInput(attrs={'placeholder': 'Empresa autorizada', 'autocomplete': 'off'}),
            'brand': forms.TextInput(attrs={'placeholder': 'Ex: Betano, Superbet', 'autocomplete': 'off'}),
            'cnpj': forms.TextInput(attrs={'placeholder': '00.000.000/0001-00', 'autocomplete': 'off'}),
            'domain': forms.TextInput(attrs={'placeholder': 'exemplo.bet.br', 'autocomplete': 'off'}),
            'alert_note': forms.TextInput(attrs={'placeholder': 'Motivo do alerta, se houver', 'autocomplete': 'off'}),
        }

    def clean_domain(self):
        domain = self.cleaned_data['domain'].strip().lower()
        return domain.replace('https://', '').replace('http://', '').strip('/')


class RegulatedImportForm(forms.Form):
    source_url = forms.URLField(
        label='URL oficial',
        required=False,
        initial='https://www.gov.br/fazenda/pt-br/composicao/orgaos/secretaria-de-premios-e-apostas/lista-de-empresas',
    )
    raw_text = forms.CharField(
        label='lista',
        required=False,
        widget=forms.Textarea(
            attrs={
                'rows': 5,
                'placeholder': 'Uma casa por linha: empresa;cnpj;marca;dominio;status\nEx: KAIZEN GAMING BRASIL LTDA;46.786.961/0001-74;Betano;br.betano.com;authorized',
            }
        ),
    )


class BookmakerAliasForm(forms.ModelForm):
    class Meta:
        model = BookmakerAlias
        fields = ['bookmaker', 'provider', 'alias', 'provider_key']
        widgets = {
            'provider': forms.TextInput(attrs={'placeholder': 'the_odds_api', 'autocomplete': 'off'}),
            'alias': forms.TextInput(attrs={'placeholder': 'Nome como aparece na API', 'autocomplete': 'off'}),
            'provider_key': forms.TextInput(attrs={'placeholder': 'Chave opcional', 'autocomplete': 'off'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['bookmaker'].queryset = RegulatedBookmaker.objects.filter(owner=user)


class PromotionPageForm(forms.ModelForm):
    class Meta:
        model = PromotionPage
        fields = ['bookmaker', 'url', 'is_active']
        widgets = {
            'url': forms.URLInput(attrs={'placeholder': 'https://casa.bet.br/promocoes', 'autocomplete': 'off'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['bookmaker'].queryset = RegulatedBookmaker.objects.filter(owner=user)


class PromotionForm(forms.ModelForm):
    class Meta:
        model = Promotion
        fields = [
            'bookmaker',
            'page',
            'title',
            'kind',
            'trigger',
            'freebet_amount',
            'min_odd',
            'sport',
            'competition',
            'suggested_game',
            'expires_at',
            'source_url',
            'source_type',
            'source_name',
            'validation_status',
            'rule_summary',
            'public_text',
            'is_active',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Ex: Perdeu, ganhou freebet', 'autocomplete': 'off'}),
            'freebet_amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'min_odd': forms.NumberInput(attrs={'step': '0.01', 'min': '1.01'}),
            'sport': forms.TextInput(attrs={'placeholder': 'Futebol', 'autocomplete': 'off'}),
            'competition': forms.TextInput(attrs={'placeholder': 'Brasileirão, Champions...', 'autocomplete': 'off'}),
            'suggested_game': forms.TextInput(attrs={'placeholder': 'Ex: Flamengo x Palmeiras', 'autocomplete': 'off'}),
            'expires_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'source_url': forms.URLInput(attrs={'placeholder': 'URL pública da promoção', 'autocomplete': 'off'}),
            'source_name': forms.TextInput(attrs={'placeholder': 'Ex: site oficial, Odds Scanner, Lance', 'autocomplete': 'off'}),
            'rule_summary': forms.TextInput(attrs={'placeholder': 'Ex: Aposta múltipla mínima, mercados elegíveis...', 'autocomplete': 'off'}),
            'public_text': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Cole o texto público da promoção para consultar depois.'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user is not None:
            bookmakers = RegulatedBookmaker.objects.filter(owner=user)
            self.fields['bookmaker'].queryset = bookmakers
            self.fields['page'].queryset = PromotionPage.objects.filter(bookmaker__owner=user)

    def clean(self):
        cleaned_data = super().clean()
        bookmaker = cleaned_data.get('bookmaker')
        page = cleaned_data.get('page')
        if bookmaker and page and page.bookmaker_id != bookmaker.id:
            self.add_error('page', 'Escolha uma página vinculada à mesma casa da promoção.')
        return cleaned_data


class PromotionExtractionForm(forms.Form):
    promotion = forms.ModelChoiceField(label='promoção', queryset=Promotion.objects.none())
    freebet_odd = forms.DecimalField(label='odd da freebet', min_value=1.01, max_digits=8, decimal_places=2, widget=forms.NumberInput(attrs={'step': '0.01', 'min': '1.01'}))
    protection_odd = forms.DecimalField(label='odd da arbitragem', min_value=1.01, max_digits=8, decimal_places=2, widget=forms.NumberInput(attrs={'step': '0.01', 'min': '1.01'}))
    protection_commission = forms.DecimalField(label='comissão arbitragem (%)', required=False, min_value=0, max_value=100, max_digits=5, decimal_places=2, initial=0, widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': '100'}))

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['promotion'].queryset = Promotion.objects.filter(
                bookmaker__owner=user,
                is_active=True,
            ).select_related('bookmaker')


class MonthlyGoalForm(forms.ModelForm):
    class Meta:
        model = MonthlyGoal
        fields = ['entity', 'month', 'profit_target', 'roi_target', 'volume_target', 'max_loss']
        widgets = {
            'entity': forms.Select(),
            'month': forms.DateInput(attrs={'type': 'date'}),
            'profit_target': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'roi_target': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'volume_target': forms.NumberInput(attrs={'min': '0'}),
            'max_loss': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['entity'].queryset = Entity.objects.filter(owner=user)
        self.fields['entity'].empty_label = 'Selecione uma entidade'

    def clean_month(self):
        month = self.cleaned_data['month']
        return month.replace(day=1)
