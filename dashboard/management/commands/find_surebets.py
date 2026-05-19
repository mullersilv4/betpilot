import os

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from dashboard.odds_api import OddsApiClient
from dashboard.odds_api import OddsApiError
from dashboard.odds_api import detect_surebets


class Command(BaseCommand):
    help = 'Busca oportunidades de surebet/arbitragem usando The Odds API.'

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
            '--bookmakers',
            default='',
            help='Casas especificas por chave canonica, separadas por virgula. Opcional.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Quantidade maxima de oportunidades para imprimir.',
        )
        parser.add_argument(
            '--stake',
            type=float,
            default=100.0,
            help='Investimento total usado para sugerir os valores por resultado.',
        )
        parser.add_argument(
            '--br-regulated-only',
            action='store_true',
            help='Considera apenas casas da whitelist inicial de regulamentadas no Brasil.',
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
            events = client.odds(
                sport_key=options['sport'],
                regions=options['regions'],
                markets='h2h',
                bookmakers=options['bookmakers'],
            )
        except OddsApiError as error:
            raise CommandError(str(error)) from error

        opportunities = detect_surebets(
            events,
            limit=options['limit'],
            brazil_regulated_only=options['br_regulated_only'],
        )
        if not opportunities:
            self.stdout.write(self.style.WARNING('Nenhuma surebet encontrada nesses filtros.'))
            return

        total_stake = options['stake']
        for opportunity in opportunities:
            implied = opportunity['implied_probability'] / 100
            expected_return = total_stake / implied

            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS(opportunity['event']))
            self.stdout.write(f'  Esporte: {opportunity["sport"]}')
            self.stdout.write(f'  Inicio: {opportunity["commence_time"]}')
            self.stdout.write(f'  Soma implicita: {opportunity["implied_probability"]:.2f}%')
            self.stdout.write(f'  Margem estimada: {opportunity["profit_margin"]:.2f}%')
            self.stdout.write(f'  Investimento total: R$ {total_stake:.2f}')
            self.stdout.write(f'  Retorno alvo: R$ {expected_return:.2f}')

            for outcome in opportunity['outcomes']:
                suggested_stake = expected_return / outcome['price']
                self.stdout.write(
                    (
                        f'    {outcome["name"]}: odd {outcome["price"]:.2f} '
                        f'em {outcome["bookmaker"]} | apostar R$ {suggested_stake:.2f}'
                    )
                )
