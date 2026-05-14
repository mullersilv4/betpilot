from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Bankroll
from .models import BankrollTransaction
from .models import Bet
from .models import MonthlyGoal


class BankrollForm(forms.ModelForm):
    class Meta:
        model = Bankroll
        fields = [
            'name',
            'bookmaker',
            'initial_balance',
            'unit_percentage',
            'max_stake_percentage',
            'daily_stop_loss_percentage',
            'weekly_stop_loss_percentage',
            'monthly_stop_loss_percentage',
            'daily_stop_win_percentage',
        ]
        widgets = {
            'name': forms.TextInput(
                attrs={
                    'placeholder': 'Ex: Banca principal',
                    'autocomplete': 'off',
                }
            ),
            'bookmaker': forms.TextInput(
                attrs={
                    'placeholder': 'Ex: Betfair, Bet365, Pinnacle',
                    'autocomplete': 'off',
                }
            ),
            'initial_balance': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'unit_percentage': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
            'max_stake_percentage': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
            'daily_stop_loss_percentage': forms.NumberInput(
                attrs={'step': '0.01', 'min': '0.01'}
            ),
            'weekly_stop_loss_percentage': forms.NumberInput(
                attrs={'step': '0.01', 'min': '0.01'}
            ),
            'monthly_stop_loss_percentage': forms.NumberInput(
                attrs={'step': '0.01', 'min': '0.01'}
            ),
            'daily_stop_win_percentage': forms.NumberInput(
                attrs={'step': '0.01', 'min': '0.01'}
            ),
        }

    def clean_initial_balance(self):
        initial_balance = self.cleaned_data['initial_balance']
        if initial_balance < 0:
            raise forms.ValidationError('O saldo inicial nao pode ser negativo.')
        return initial_balance

    def clean(self):
        cleaned_data = super().clean()
        unit_percentage = cleaned_data.get('unit_percentage')
        max_stake_percentage = cleaned_data.get('max_stake_percentage')

        if unit_percentage and max_stake_percentage and unit_percentage > max_stake_percentage:
            self.add_error(
                'unit_percentage',
                'A unidade padrao nao pode ser maior que a stake maxima.',
            )

        return cleaned_data


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=False)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')


class BetForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['bankroll'].queryset = Bankroll.objects.filter(owner=user)
        if self.instance and self.instance.event_date:
            self.initial['event_date'] = self.instance.event_date.strftime('%Y-%m-%dT%H:%M')

    class Meta:
        model = Bet
        fields = [
            'bankroll',
            'sport',
            'competition',
            'game',
            'market',
            'strategy',
            'event_date',
            'entry_type',
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
                    'placeholder': 'Ex: Brasileirao, NBA, ATP',
                    'autocomplete': 'off',
                }
            ),
            'game': forms.TextInput(
                attrs={
                    'placeholder': 'Ex: Palmeiras x Flamengo',
                    'autocomplete': 'off',
                }
            ),
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
            'event_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
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

        available_balance = bankroll.available_balance if bankroll else 0
        if (
            bankroll
            and self.instance.pk
            and self.instance.bankroll_id == bankroll.id
            and self.instance.status == Bet.Status.OPEN
        ):
            available_balance += self.instance.stake

        if bankroll and stake and stake > available_balance:
            self.add_error(
                'stake',
                'O valor da aposta nao pode ser maior que o saldo disponivel da banca.',
            )

        if bankroll and stake and stake > bankroll.max_stake_amount:
            self.add_error(
                'stake',
                f'A stake maxima configurada para esta banca e R$ {bankroll.max_stake_amount}.',
            )

        if bankroll and stake and not self.instance.pk and bankroll.risk_lock_active:
            self.add_error(
                'bankroll',
                'Esta banca esta com stop loss/stop win ativo. Revise a gestao antes de apostar.',
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
        if user is not None:
            self.fields['bankroll'].queryset = Bankroll.objects.filter(owner=user)
        self.fields['kind'].choices = [
            (BankrollTransaction.Kind.DEPOSIT, 'Deposito'),
            (BankrollTransaction.Kind.WITHDRAW, 'Saque'),
            (BankrollTransaction.Kind.ADJUSTMENT, 'Ajuste'),
        ]

    class Meta:
        model = BankrollTransaction
        fields = ['bankroll', 'kind', 'amount', 'note']
        widgets = {
            'bankroll': forms.Select(),
            'kind': forms.Select(),
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
        amount = cleaned_data.get('amount')

        if (
            bankroll
            and amount
            and kind in {BankrollTransaction.Kind.WITHDRAW, BankrollTransaction.Kind.TRANSFER_OUT}
            and amount > bankroll.available_balance
        ):
            self.add_error(
                'amount',
                'O valor nao pode ser maior que o saldo disponivel da banca.',
            )

        return cleaned_data


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
                'A transferencia nao pode ser maior que o saldo disponivel.',
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
    competition = forms.CharField(label='competicao', required=False)
    strategy = forms.CharField(label='estrategia', required=False)
    market = forms.CharField(label='mercado', required=False)
    query = forms.CharField(label='busca', required=False)
    min_odds = forms.DecimalField(label='odd min.', required=False, min_value=1.01)
    max_odds = forms.DecimalField(label='odd max.', required=False, min_value=1.01)

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
                    'Uma aposta por linha: banca;jogo;mercado;odd;valor;comissao;status\n'
                    'Formato novo: banca;esporte;competicao;jogo;mercado;estrategia;tipo;data;odd;valor;comissao;status\n'
                    'Ex: Banca principal;Futebol;Brasileirao;Palmeiras x Flamengo;Over 2.5;Modelo gols;pre_match;2026-05-13 21:30;1.90;100;5;open'
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


class MonthlyGoalForm(forms.ModelForm):
    class Meta:
        model = MonthlyGoal
        fields = ['bankroll', 'month', 'profit_target', 'roi_target', 'volume_target', 'max_loss']
        widgets = {
            'bankroll': forms.Select(),
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
            self.fields['bankroll'].queryset = Bankroll.objects.filter(owner=user)

    def clean_month(self):
        month = self.cleaned_data['month']
        return month.replace(day=1)
