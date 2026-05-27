from decimal import Decimal
from datetime import timedelta
import time

from django.utils import timezone

from .bookmaker_adapters import iter_adapters
from .bookmaker_adapters.base import BookmakerAdapterError
from .models import BookmakerEventLink
from .models import OddsSnapshot


DEFAULT_BOOKMAKERS = [
    'betano',
    'superbet',
    'bet365',
    'novibet',
    'betfair',
    'estrelabet',
    'esportesdasorte',
]

DEFAULT_MARKETS = ['Resultado Final']
EVENT_LINK_CACHE_TTL = timedelta(hours=24)


def normalize_bookmaker_list(bookmakers):
    if not bookmakers:
        return DEFAULT_BOOKMAKERS
    if isinstance(bookmakers, str):
        return [item.strip() for item in bookmakers.split(',') if item.strip()]
    return list(bookmakers)


def normalize_selection(selection, event):
    normalized = (selection or '').strip().lower()
    home_team = event['home_team']
    away_team = event['away_team']
    home_terms = {
        '1',
        'casa',
        'mandante',
        home_team.lower(),
    }
    away_terms = {
        '2',
        'fora',
        'visitante',
        away_team.lower(),
    }
    draw_terms = {'x', 'empate', 'draw'}
    if normalized in home_terms:
        return home_team
    if normalized in away_terms:
        return away_team
    if normalized in draw_terms:
        return 'Empate'
    return selection


def cached_event_link(event, bookmaker):
    threshold = timezone.now() - EVENT_LINK_CACHE_TTL
    link = BookmakerEventLink.objects.filter(
        external_event_id=event['external_event_id'],
        bookmaker=bookmaker,
        status=BookmakerEventLink.Status.FOUND,
        event_url__gt='',
        last_checked_at__gte=threshold,
    ).first()
    return link


def find_or_refresh_event_links(event, bookmakers=None):
    links = []
    bookmaker_keys = normalize_bookmaker_list(bookmakers)
    for adapter in iter_adapters(bookmaker_keys):
        cached_link = cached_event_link(event, adapter.bookmaker)
        if cached_link:
            links.append(cached_link)
            continue

        defaults = {
            'home_team': event['home_team'],
            'away_team': event['away_team'],
            'last_checked_at': timezone.now(),
        }
        try:
            time.sleep(adapter.request_delay_seconds)
            match = adapter.find_event(
                event['home_team'],
                event['away_team'],
                event.get('start_time'),
            )
        except (BookmakerAdapterError, OSError) as error:
            defaults.update(
                {
                    'status': BookmakerEventLink.Status.ERROR,
                    'last_error': str(error)[:220],
                }
            )
        else:
            if match:
                defaults.update(
                    {
                        'event_url': match.event_url,
                        'matched_confidence': match.matched_confidence,
                        'status': BookmakerEventLink.Status.FOUND,
                        'last_error': '',
                    }
                )
            else:
                defaults.update(
                    {
                        'matched_confidence': Decimal('0.00'),
                        'status': BookmakerEventLink.Status.NOT_FOUND,
                        'last_error': '',
                    }
                )

        link, _created = BookmakerEventLink.objects.update_or_create(
            external_event_id=event['external_event_id'],
            bookmaker=adapter.bookmaker,
            defaults=defaults,
        )
        links.append(link)
    return links


def capture_event_odds(event, bookmakers=None, markets=None):
    markets = markets or DEFAULT_MARKETS
    links = find_or_refresh_event_links(event, bookmakers=bookmakers)
    snapshots = []

    for link in links:
        if link.status != BookmakerEventLink.Status.FOUND or not link.event_url:
            continue
        adapter = next(iter_adapters([link.bookmaker]), None)
        if not adapter:
            continue
        try:
            quotes = adapter.get_event_odds(link.event_url, markets=markets)
        except (BookmakerAdapterError, OSError) as error:
            link.status = BookmakerEventLink.Status.ERROR
            link.last_error = str(error)[:220]
            link.last_checked_at = timezone.now()
            link.save(update_fields=['status', 'last_error', 'last_checked_at'])
            continue

        for quote in quotes:
            snapshots.append(
                OddsSnapshot.objects.create(
                    external_event_id=event['external_event_id'],
                    bookmaker=quote.bookmaker,
                    market=quote.market,
                    selection=normalize_selection(quote.selection, event),
                    odd=quote.odd,
                    source_url=quote.source_url,
                )
            )
        link.last_checked_at = timezone.now()
        link.save(update_fields=['last_checked_at'])

    return snapshots


def latest_event_odds(external_event_id, market='Resultado Final'):
    latest_ids = []
    pairs = (
        OddsSnapshot.objects.filter(external_event_id=external_event_id, market=market)
        .values_list('bookmaker', 'selection')
        .distinct()
    )
    for bookmaker, selection in pairs:
        snapshot = (
            OddsSnapshot.objects.filter(
                external_event_id=external_event_id,
                bookmaker=bookmaker,
                market=market,
                selection=selection,
            )
            .order_by('-captured_at')
            .first()
        )
        if snapshot:
            latest_ids.append(snapshot.id)
    return OddsSnapshot.objects.filter(id__in=latest_ids).order_by('bookmaker', 'selection')
