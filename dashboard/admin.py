from django.contrib import admin

from .models import Bankroll
from .models import BankrollTransaction
from .models import Bet
from .models import BookmakerAlias
from .models import BookmakerEventLink
from .models import Entity
from .models import FreeBet
from .models import MonthlyGoal
from .models import OddsSnapshot
from .models import Promotion
from .models import PromotionPage
from .models import RegulatedBookmaker
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


@admin.register(RegulatedBookmaker)
class RegulatedBookmakerAdmin(admin.ModelAdmin):
    list_display = ('owner', 'brand', 'domain', 'status', 'judicial_alert', 'last_checked_at')
    list_filter = ('status', 'judicial_alert')
    search_fields = ('owner__username', 'brand', 'company_name', 'cnpj', 'domain')


@admin.register(BookmakerAlias)
class BookmakerAliasAdmin(admin.ModelAdmin):
    list_display = ('bookmaker', 'provider', 'alias', 'provider_key', 'created_at')
    list_filter = ('provider',)
    search_fields = ('bookmaker__brand', 'alias', 'provider_key')


@admin.register(BookmakerEventLink)
class BookmakerEventLinkAdmin(admin.ModelAdmin):
    list_display = (
        'external_event_id',
        'bookmaker',
        'home_team',
        'away_team',
        'status',
        'matched_confidence',
        'last_checked_at',
    )
    list_filter = ('bookmaker', 'status')
    search_fields = ('external_event_id', 'bookmaker', 'home_team', 'away_team', 'event_url')


@admin.register(OddsSnapshot)
class OddsSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        'external_event_id',
        'bookmaker',
        'market',
        'selection',
        'odd',
        'captured_at',
    )
    list_filter = ('bookmaker', 'market', 'captured_at')
    search_fields = ('external_event_id', 'bookmaker', 'market', 'selection', 'source_url')


@admin.register(PromotionPage)
class PromotionPageAdmin(admin.ModelAdmin):
    list_display = ('bookmaker', 'url', 'is_active', 'last_scan_at', 'last_scan_note')
    list_filter = ('is_active', 'bookmaker')
    search_fields = ('bookmaker__brand', 'url', 'last_scan_note')


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = (
        'bookmaker',
        'title',
        'kind',
        'trigger',
        'freebet_amount',
        'min_odd',
        'source_type',
        'validation_status',
        'expires_at',
        'is_active',
        'detected_at',
    )
    list_filter = ('kind', 'trigger', 'source_type', 'validation_status', 'expires_at', 'is_active', 'bookmaker')
    search_fields = ('bookmaker__brand', 'title', 'competition', 'suggested_game', 'source_name', 'rule_summary', 'public_text')


@admin.register(SureBetEntry)
class SureBetEntryAdmin(admin.ModelAdmin):
    list_display = (
        'bet',
        'bankroll',
        'bookmaker',
        'label',
        'mode',
        'odds',
        'stake',
        'liability',
        'return_amount',
        'net_result',
        'freebet_enabled',
        'freebet_amount',
        'is_winner',
    )
    list_filter = ('bookmaker', 'bankroll', 'mode', 'freebet_enabled', 'is_winner')
    search_fields = ('bookmaker', 'label', 'bet__game')


@admin.register(BankrollTransaction)
class BankrollTransactionAdmin(admin.ModelAdmin):
    list_display = ('bankroll', 'kind', 'amount', 'note', 'created_at')
    list_filter = ('kind', 'created_at')
    search_fields = ('bankroll__name', 'note')


@admin.register(MonthlyGoal)
class MonthlyGoalAdmin(admin.ModelAdmin):
    list_display = (
        'entity',
        'month',
        'profit_target',
        'roi_target',
        'volume_target',
        'max_loss',
        'profit',
        'roi',
        'volume',
    )
    list_filter = ('month', 'entity')

# Register your models here.
