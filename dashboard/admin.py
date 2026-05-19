from django.contrib import admin

from .models import Bankroll
from .models import BankrollTransaction
from .models import Bet
from .models import Entity
from .models import FreeBet
from .models import MonthlyGoal
from .models import SureBetEntry


@admin.register(Entity)
class EntityAdmin(admin.ModelAdmin):
    list_display = ('owner', 'name', 'notes', 'created_at')
    search_fields = ('owner__username', 'name', 'notes')


@admin.register(Bankroll)
class BankrollAdmin(admin.ModelAdmin):
    list_display = (
        'owner',
        'entity',
        'name',
        'bookmaker',
        'initial_balance',
        'current_balance',
        'available_balance',
        'created_at',
    )
    fieldsets = (
        (
            None,
            {
                'fields': (
                    'name',
                    'entity',
                    'bookmaker',
                    'initial_balance',
                )
            },
        ),
    )
    search_fields = ('owner__username', 'name', 'bookmaker')


@admin.register(Bet)
class BetAdmin(admin.ModelAdmin):
    list_display = (
        'bankroll',
        'sport',
        'competition',
        'game',
        'market',
        'entry_type',
        'odds',
        'stake',
        'exchange_commission',
        'status',
        'created_at',
    )
    list_filter = ('status', 'sport', 'entry_type', 'created_at')
    search_fields = ('game', 'market', 'competition', 'strategy')


@admin.register(FreeBet)
class FreeBetAdmin(admin.ModelAdmin):
    list_display = ('bookmaker', 'amount', 'is_used', 'source_bet', 'created_at')
    list_filter = ('is_used', 'bookmaker', 'created_at')
    search_fields = ('bookmaker', 'source_bet__game')


@admin.register(SureBetEntry)
class SureBetEntryAdmin(admin.ModelAdmin):
    list_display = (
        'bet',
        'bookmaker',
        'label',
        'odds',
        'stake',
        'return_amount',
        'net_result',
        'freebet_enabled',
        'freebet_amount',
        'is_winner',
    )
    list_filter = ('bookmaker', 'freebet_enabled', 'is_winner')
    search_fields = ('bookmaker', 'label', 'bet__game')


@admin.register(BankrollTransaction)
class BankrollTransactionAdmin(admin.ModelAdmin):
    list_display = ('bankroll', 'kind', 'amount', 'note', 'created_at')
    list_filter = ('kind', 'created_at')
    search_fields = ('bankroll__name', 'note')


@admin.register(MonthlyGoal)
class MonthlyGoalAdmin(admin.ModelAdmin):
    list_display = (
        'bankroll',
        'month',
        'profit_target',
        'roi_target',
        'volume_target',
        'max_loss',
        'profit',
        'roi',
        'volume',
    )
    list_filter = ('month', 'bankroll')

# Register your models here.
