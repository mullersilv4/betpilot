import os

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from dashboard.models import Bet
from dashboard.odds_api import OddsApiClient
from dashboard.odds_api import OddsApiError
from dashboard.result_settlement import apply_settlement
from dashboard.result_settlement import resolve_bet_from_event


class Command(BaseCommand):
    help = 'Fecha apostas abertas quando o jogo ja terminou e o mercado simples foi resolvido.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days-from',
            type=int,
            default=3,
            choices=[1, 2, 3],
            help='Quantidade de dias para buscar jogos finalizados. Maximo permitido pela API: 3.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostra o que seria fechado sem alterar o banco.',
        )

    def handle(self, *args, **options):
        api_key = os.environ.get('THE_ODDS_API_KEY')
        if not api_key:
            raise CommandError('Defina THE_ODDS_API_KEY antes de rodar.')

        pending_bets = Bet.objects.filter(
            status=Bet.Status.OPEN,
            external_event_id__gt='',
            external_sport_key__gt='',
        ).exclude(strategy='Surebet')
        if not pending_bets.exists():
            self.stdout.write(self.style.WARNING('Nenhuma aposta aberta com evento externo.'))
            return

        client = OddsApiClient(api_key=api_key)
        settled_count = 0
        skipped_count = 0

        sport_keys = pending_bets.values_list('external_sport_key', flat=True).distinct()
        for sport_key in sport_keys:
            sport_bets = list(pending_bets.filter(external_sport_key=sport_key))
            event_ids = sorted({bet.external_event_id for bet in sport_bets})
            try:
                events = client.scores(
                    sport_key,
                    days_from=options['days_from'],
                    event_ids=event_ids,
                )
            except OddsApiError as error:
                self.stderr.write(self.style.ERROR(f'{sport_key}: {error}'))
                skipped_count += len(sport_bets)
                continue

            events_by_id = {event.get('id'): event for event in events}
            for bet in sport_bets:
                event = events_by_id.get(bet.external_event_id)
                decision = resolve_bet_from_event(bet, event or {})
                if decision is None:
                    skipped_count += 1
                    continue

                if options['dry_run']:
                    self.stdout.write(
                        f'[dry-run] {bet.game} | {bet.market} -> {decision.status}'
                    )
                else:
                    apply_settlement(bet, decision)
                    self.stdout.write(f'{bet.game} | {bet.market} -> {bet.get_status_display()}')
                settled_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Finalizado: {settled_count} aposta(s) resolvida(s), {skipped_count} mantida(s) aberta(s).'
            )
        )
