import json
import os

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from dashboard.odds_api import OddsApiClient
from dashboard.odds_api import OddsApiError
from dashboard.odds_api import summarize_odds


class Command(BaseCommand):
    help = 'Testa a conexao com The Odds API e lista jogos/odds.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sport',
            default='soccer_epl',
            help='Sport key da API. Ex: soccer_epl, soccer_brazil_campeonato, basketball_nba.',
        )
        parser.add_argument(
            '--regions',
            default='eu',
            help='Regioes das casas. Ex: us, uk, eu, au ou combinacoes com virgula.',
        )
        parser.add_argument(
            '--markets',
            default='h2h',
            help='Mercados. Ex: h2h, spreads, totals.',
        )
        parser.add_argument(
            '--bookmakers',
            default='',
            help='Casas especificas por chave canonica, separadas por virgula. Opcional.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=5,
            help='Quantidade maxima de jogos para imprimir.',
        )
        parser.add_argument(
            '--list-sports',
            action='store_true',
            help='Lista esportes disponiveis na sua chave em vez de odds.',
        )

    def handle(self, *args, **options):
        api_key = os.environ.get('THE_ODDS_API_KEY')
        if not api_key:
            raise CommandError(
                'Defina THE_ODDS_API_KEY antes de rodar. '
                'Ex: $env:THE_ODDS_API_KEY="sua_chave"'
            )

        client = OddsApiClient(api_key=api_key)

        try:
            if options['list_sports']:
                sports = client.sports()
                self.stdout.write(json.dumps(sports[: options['limit']], indent=2, ensure_ascii=False))
                return

            events = client.odds(
                sport_key=options['sport'],
                regions=options['regions'],
                markets=options['markets'],
                bookmakers=options['bookmakers'],
            )
        except OddsApiError as error:
            raise CommandError(str(error)) from error

        summaries = summarize_odds(events, limit=options['limit'])
        if not summaries:
            self.stdout.write(self.style.WARNING('Nenhum jogo/odd retornado para esses filtros.'))
            return

        for item in summaries:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS(item['event']))
            self.stdout.write(f'  Esporte: {item["sport"]}')
            self.stdout.write(f'  Inicio: {item["commence_time"]}')
            for bookmaker in item['bookmakers']:
                self.stdout.write(f'  Casa: {bookmaker["title"]}')
                for market in bookmaker['markets']:
                    self.stdout.write(f'    Mercado {market["key"]}: {", ".join(market["outcomes"])}')
