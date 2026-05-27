import json
import os
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.utils import timezone

from dashboard.odds_api import BRAZIL_PRIORITY_BOOKMAKER_TERMS
from dashboard.odds_api import BRAZIL_REGULATED_BOOKMAKER_NAMES
from dashboard.odds_api import OddsApiError
from dashboard.odds_api import OddsPapiClient
from dashboard.odds_api import normalize_bookmaker_text


def bookmaker_matches_terms(bookmaker, terms):
    slug = normalize_bookmaker_text(bookmaker.get('slug'))
    name = normalize_bookmaker_text(bookmaker.get('bookmakerName'))
    return any(term and (term == slug or term == name or term in slug or term in name) for term in terms)


def count_bookmaker_prices(bookmaker_payload):
    price_count = 0
    market_count = 0
    for market in bookmaker_payload.get('markets', {}).values():
        market_count += 1
        for outcome in market.get('outcomes', {}).values():
            for player in outcome.get('players', {}).values():
                if player.get('price') is not None:
                    price_count += 1
    return market_count, price_count


def summarize_fixture(fixture):
    home = fixture.get('participant1Name') or fixture.get('participant1ShortName') or 'Time 1'
    away = fixture.get('participant2Name') or fixture.get('participant2ShortName') or 'Time 2'
    tournament = fixture.get('tournamentName') or fixture.get('tournamentSlug') or 'Torneio'
    return f'{home} x {away} | {tournament} | {fixture.get("startTime") or "-"}'


class Command(BaseCommand):
    help = 'Testa a OddsPapi e verifica se ela retorna casas/odds de casas brasileiras.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--list-bookmakers',
            action='store_true',
            help='Lista casas brasileiras prováveis encontradas no cadastro da OddsPapi.',
        )
        parser.add_argument(
            '--list-sports',
            action='store_true',
            help='Lista esportes disponíveis na OddsPapi.',
        )
        parser.add_argument(
            '--list-tournaments',
            action='store_true',
            help='Lista torneios do esporte informado.',
        )
        parser.add_argument(
            '--sport-id',
            type=int,
            default=10,
            help='ID do esporte na OddsPapi. Futebol geralmente é 10.',
        )
        parser.add_argument(
            '--tournament-id',
            type=int,
            default=None,
            help='ID do torneio para buscar fixtures. Ex: usar após --list-tournaments.',
        )
        parser.add_argument(
            '--tournament-ids',
            default='',
            help='IDs de torneios separados por vírgula para testar /odds-by-tournaments.',
        )
        parser.add_argument(
            '--fixture-id',
            default='',
            help='ID de um fixture específico para testar /odds.',
        )
        parser.add_argument(
            '--bookmakers',
            default='',
            help='Slugs de casas separados por vírgula. Vazio busca todas as casas disponíveis.',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=2,
            help='Janela de dias futuros para buscar fixtures quando não há fixture/tournament específico.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=5,
            help='Quantidade máxima de itens para imprimir.',
        )
        parser.add_argument(
            '--json',
            action='store_true',
            help='Imprime o JSON bruto do endpoint principal chamado.',
        )

    def handle(self, *args, **options):
        api_key = os.environ.get('ODDSPAPI_API_KEY') or os.environ.get('ODDS_PAPI_API_KEY')
        if not api_key:
            raise CommandError(
                'Defina ODDSPAPI_API_KEY antes de rodar. '
                'Ex: export ODDSPAPI_API_KEY="sua_chave"'
            )

        client = OddsPapiClient(api_key=api_key)
        brazil_terms = sorted(
            {
                normalize_bookmaker_text(term)
                for term in BRAZIL_PRIORITY_BOOKMAKER_TERMS.union(BRAZIL_REGULATED_BOOKMAKER_NAMES)
            }
        )

        try:
            if options['list_sports']:
                sports = client.sports()
                self.stdout.write(json.dumps(sports[: options['limit']], indent=2, ensure_ascii=False))
                return

            if options['list_tournaments']:
                tournaments = client.tournaments(options['sport_id'])
                if options['json']:
                    self.stdout.write(json.dumps(tournaments, indent=2, ensure_ascii=False))
                    return
                for tournament in tournaments[: options['limit']]:
                    self.stdout.write(
                        (
                            f'{tournament.get("tournamentId")} | '
                            f'{tournament.get("tournamentName")} | '
                            f'{tournament.get("categoryName")} | '
                            f'upcoming={tournament.get("upcomingFixtures")}'
                        )
                    )
                return

            bookmakers = client.bookmakers()
            brazil_bookmakers = [
                bookmaker for bookmaker in bookmakers if bookmaker_matches_terms(bookmaker, brazil_terms)
            ]

            if options['list_bookmakers']:
                if not brazil_bookmakers:
                    self.stdout.write(self.style.WARNING('Nenhuma casa brasileira provável encontrada.'))
                    return
                self.stdout.write(self.style.SUCCESS(f'{len(brazil_bookmakers)} casa(s) brasileira(s) prováveis:'))
                for bookmaker in brazil_bookmakers:
                    live = bookmaker.get('liveOdds')
                    self.stdout.write(
                        f'  {bookmaker.get("slug")} | {bookmaker.get("bookmakerName")} | liveOdds={live}'
                    )
                return

            payload = None
            if options['fixture_id']:
                payload = client.odds(
                    fixture_id=options['fixture_id'],
                    bookmakers=options['bookmakers'],
                )
                events = [payload]
            elif options['tournament_ids']:
                payload = client.odds_by_tournaments(
                    tournament_ids=options['tournament_ids'],
                    bookmakers=options['bookmakers'],
                )
                events = payload if isinstance(payload, list) else [payload]
            else:
                now = timezone.now()
                fixtures = client.fixtures(
                    sport_id=options['sport_id'],
                    tournament_id=options['tournament_id'],
                    from_time=now.strftime('%Y-%m-%dT%H:%M:%SZ'),
                    to_time=(now + timedelta(days=options['days'])).strftime('%Y-%m-%dT%H:%M:%SZ'),
                    bookmakers=options['bookmakers'],
                )
                if not fixtures:
                    self.stdout.write(self.style.WARNING('Nenhum fixture com odds encontrado nessa janela.'))
                    return
                events = []
                for fixture in fixtures[: options['limit']]:
                    self.stdout.write('')
                    self.stdout.write(self.style.SUCCESS(summarize_fixture(fixture)))
                    event_payload = client.odds(
                        fixture_id=fixture['fixtureId'],
                        bookmakers=options['bookmakers'],
                    )
                    events.append(event_payload)
                payload = events

        except OddsApiError as error:
            raise CommandError(str(error)) from error

        if options['json']:
            self.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False))
            return

        if not events:
            self.stdout.write(self.style.WARNING('Nenhuma odd retornada.'))
            return

        found_brazil_slugs = set()
        all_bookmaker_slugs = set()
        for event in events[: options['limit']]:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS(summarize_fixture(event)))
            bookmaker_odds = event.get('bookmakerOdds') or {}
            if not bookmaker_odds:
                self.stdout.write('  Sem bookmakerOdds no payload.')
                continue
            for slug, bookmaker_payload in sorted(bookmaker_odds.items()):
                all_bookmaker_slugs.add(slug)
                market_count, price_count = count_bookmaker_prices(bookmaker_payload)
                marker = ''
                if normalize_bookmaker_text(slug) in brazil_terms:
                    found_brazil_slugs.add(slug)
                    marker = ' [BR?]'
                self.stdout.write(
                    f'  {slug}{marker}: {market_count} mercado(s), {price_count} preço(s)'
                )

        if found_brazil_slugs:
            self.stdout.write('')
            self.stdout.write(
                self.style.SUCCESS(
                    'Casas brasileiras/prováveis com odds no retorno: '
                    f'{", ".join(sorted(found_brazil_slugs))}'
                )
            )
        else:
            self.stdout.write('')
            self.stdout.write(
                self.style.WARNING(
                    'Nenhuma casa brasileira provável apareceu com odds nesse teste. '
                    'Tente informar --bookmakers com slugs vistos em --list-bookmakers.'
                )
            )
        self.stdout.write(f'Total de casas no payload: {len(all_bookmaker_slugs)}')
