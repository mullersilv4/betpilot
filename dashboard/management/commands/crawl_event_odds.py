from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.utils import timezone

from dashboard.models import BookmakerEventLink
from dashboard.odds_crawler import DEFAULT_BOOKMAKERS
from dashboard.odds_crawler import capture_event_odds
from dashboard.odds_crawler import normalize_bookmaker_list


class Command(BaseCommand):
    help = 'Captura odds públicas via adapters de casas para um evento conhecido.'

    def add_arguments(self, parser):
        parser.add_argument('--event-id', required=True, help='ID externo do evento/agendamento.')
        parser.add_argument('--home-team', required=True, help='Mandante.')
        parser.add_argument('--away-team', required=True, help='Visitante.')
        parser.add_argument('--start-time', default='', help='Data/hora do evento, se disponível.')
        parser.add_argument(
            '--bookmakers',
            default=','.join(DEFAULT_BOOKMAKERS),
            help='Adapters separados por vírgula. Ex: betano,superbet,bet365.',
        )
        parser.add_argument(
            '--markets',
            default='Resultado Final',
            help='Mercados separados por vírgula. MVP: Resultado Final.',
        )
        parser.add_argument(
            '--event-url',
            default='',
            help='URL pública do evento em uma casa. Use com apenas uma casa em --bookmakers.',
        )

    def handle(self, *args, **options):
        bookmakers = normalize_bookmaker_list(options['bookmakers'])
        markets = [market.strip() for market in options['markets'].split(',') if market.strip()]
        if not bookmakers:
            raise CommandError('Informe ao menos uma casa em --bookmakers.')
        if options['event_url'] and len(bookmakers) != 1:
            raise CommandError('Use --event-url com apenas uma casa em --bookmakers.')

        event = {
            'external_event_id': options['event_id'],
            'home_team': options['home_team'],
            'away_team': options['away_team'],
            'start_time': options['start_time'],
        }
        if options['event_url']:
            BookmakerEventLink.objects.update_or_create(
                external_event_id=event['external_event_id'],
                bookmaker=bookmakers[0],
                defaults={
                    'home_team': event['home_team'],
                    'away_team': event['away_team'],
                    'event_url': options['event_url'],
                    'matched_confidence': '100.00',
                    'status': BookmakerEventLink.Status.FOUND,
                    'last_error': '',
                    'last_checked_at': timezone.now(),
                },
            )
        snapshots = capture_event_odds(event, bookmakers=bookmakers, markets=markets)
        if not snapshots:
            self.stdout.write(
                self.style.WARNING(
                    'Nenhuma odd capturada. Verifique os links gerados em BookmakerEventLink '
                    'ou implemente o adapter da casa desejada.'
                )
            )
            return

        self.stdout.write(self.style.SUCCESS(f'{len(snapshots)} odd(s) capturada(s).'))
        for snapshot in snapshots:
            self.stdout.write(
                f'{snapshot.bookmaker} | {snapshot.market} | {snapshot.selection} | {snapshot.odd}'
            )
