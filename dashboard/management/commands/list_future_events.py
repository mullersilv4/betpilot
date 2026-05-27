import os
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from dashboard.odds_api import OddsApiClient
from dashboard.odds_api import OddsApiError
from dashboard.odds_api import OddsPapiClient


SPORT_CHOICES = {
    'brasileirao': ('soccer_brazil_campeonato', 10),
    'premier': ('soccer_epl', 10),
    'champions': ('soccer_uefa_champs_league', 10),
}


def get_oddspapi_api_key():
    return os.environ.get('ODDSPAPI_API_KEY') or os.environ.get('ODDS_PAPI_API_KEY')


def format_date(value):
    if not value:
        return '-'
    parsed = parse_datetime(value)
    if not parsed:
        return value
    return timezone.localtime(parsed).strftime('%d/%m/%Y %H:%M')


class Command(BaseCommand):
    help = 'Lista jogos futuros disponíveis nas fontes de agenda.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sport',
            default='brasileirao',
            choices=SPORT_CHOICES.keys(),
            help='Agenda a consultar.',
        )
        parser.add_argument('--days', type=int, default=14, help='Janela futura em dias para OddsPapi.')
        parser.add_argument('--limit', type=int, default=20, help='Quantidade máxima por fonte.')

    def handle(self, *args, **options):
        sport_key, oddspapi_sport_id = SPORT_CHOICES[options['sport']]
        limit = options['limit']
        now = timezone.now()

        odds_api_key = os.environ.get('THE_ODDS_API_KEY')
        if odds_api_key:
            self.stdout.write(self.style.SUCCESS('The Odds API'))
            client = OddsApiClient(odds_api_key)
            try:
                events = client.events(sport_key)
            except OddsApiError as error:
                self.stdout.write(self.style.WARNING(str(error)))
                events = []
            future_events = []
            for event in events:
                starts_at = parse_datetime(event.get('commence_time') or '')
                if starts_at and starts_at >= now:
                    future_events.append(event)
            future_events.sort(key=lambda item: item.get('commence_time') or '')
            for event in future_events[:limit]:
                self.stdout.write(
                    (
                        f'{event.get("id")} | '
                        f'{event.get("home_team")} x {event.get("away_team")} | '
                        f'{format_date(event.get("commence_time"))}'
                    )
                )
        else:
            self.stdout.write(self.style.WARNING('THE_ODDS_API_KEY não configurada.'))

        oddspapi_key = get_oddspapi_api_key()
        if oddspapi_key:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('OddsPapi'))
            client = OddsPapiClient(oddspapi_key)
            from_time = now.strftime('%Y-%m-%dT%H:%M:%SZ')
            to_time = (now + timedelta(days=options['days'])).strftime('%Y-%m-%dT%H:%M:%SZ')
            try:
                events = client.fixtures(
                    sport_id=oddspapi_sport_id,
                    from_time=from_time,
                    to_time=to_time,
                    status_id=0,
                    has_odds=True,
                )
            except OddsApiError as error:
                self.stdout.write(self.style.WARNING(str(error)))
                events = []
            events.sort(key=lambda item: item.get('startTime') or '')
            for event in events[:limit]:
                home = event.get('participant1Name') or event.get('participant1ShortName') or 'Mandante'
                away = event.get('participant2Name') or event.get('participant2ShortName') or 'Visitante'
                self.stdout.write(
                    f'{event.get("fixtureId")} | {home} x {away} | {format_date(event.get("startTime"))}'
                )
        else:
            self.stdout.write(self.style.WARNING('ODDSPAPI_API_KEY não configurada.'))
