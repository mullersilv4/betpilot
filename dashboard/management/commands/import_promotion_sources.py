import ast
from pathlib import Path
from urllib.parse import urlparse

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.utils import timezone

from dashboard.bookmaker_import import slug_alias
from dashboard.models import PromotionPage
from dashboard.models import RegulatedBookmaker


DEFAULT_SOURCES = [
    {"brand": "bet365", "url": "https://www.bet365.bet.br/promos/pt-br/home", "status": "confirmed"},
    {"brand": "betano", "url": "https://www.betano.bet.br/promocoes/", "status": "confirmed"},
    {"brand": "superbet", "url": "https://superbet.bet.br/promocoes-e-bonus", "status": "confirmed"},
    {"brand": "novibet", "url": "https://www.novibet.bet.br/apostas-esportivas/promocoes", "status": "confirmed"},
    {"brand": "jogo_de_ouro", "url": "https://jogodeouro.bet.br/pt/promotions/all", "status": "confirmed"},
    {"brand": "bolsa_de_aposta", "url": "https://bolsadeaposta.bet.br/", "status": "needs_manual_check"},
    {"brand": "betfair_promos", "url": "https://promos.betfair.bet.br/", "status": "partial"},
    {"brand": "betfair_casino", "url": "https://casino.betfair.bet.br/promocoes", "status": "confirmed"},
    {"brand": "pagol", "url": "https://pago.bet.br/", "status": "needs_manual_check"},
    {"brand": "sportingbet", "url": "https://www.sportingbet.bet.br/pt-br/promo/offers", "status": "confirmed"},
    {"brand": "sportingbet_sportsbook", "url": "https://www.sportingbet.bet.br/pt-br/promo/offers/p/sportsbook", "status": "confirmed"},
    {"brand": "estrela_bet", "url": "https://www.estrelabet.bet.br/offers", "status": "confirmed"},
    {"brand": "estrela_bet_bonus", "url": "https://www.estrelabet.bet.br/pagina/bonus-estrela-bet", "status": "confirmed"},
    {"brand": "esportes_da_sorte", "url": "https://m.esportesdasorte.bet.br/ptb/contents/promotions", "status": "confirmed"},
]


def hostname_from_url(url):
    return (urlparse(url).hostname or '').lower().removeprefix('www.').removeprefix('m.')


def find_bookmaker(user, brand, url):
    host = hostname_from_url(url)
    host_parts = host.split('.')
    domain_candidates = ['.'.join(host_parts[index:]) for index in range(len(host_parts))]
    bookmakers = RegulatedBookmaker.objects.filter(owner=user)

    for candidate in domain_candidates:
        bookmaker = bookmakers.filter(domain__iexact=candidate).first()
        if bookmaker:
            return bookmaker

    clean_brand = slug_alias(brand.replace('_promos', '').replace('_casino', '').replace('_sportsbook', '').replace('_bonus', ''))
    for bookmaker in bookmakers:
        if slug_alias(bookmaker.brand) == clean_brand:
            return bookmaker
    for bookmaker in bookmakers:
        if clean_brand and clean_brand in slug_alias(bookmaker.brand):
            return bookmaker
    return None


class Command(BaseCommand):
    help = 'Importa URLs públicas de promoções e vincula às casas regulamentadas.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True, help='Usuário dono dos cadastros.')
        parser.add_argument('--sources-file', help='Arquivo com uma lista Python/JSON de sources.', default='')

    def handle(self, *args, **options):
        User = get_user_model()
        try:
            user = User.objects.get(username=options['username'])
        except User.DoesNotExist as exc:
            raise CommandError(f'Usuário não encontrado: {options["username"]}') from exc

        sources = DEFAULT_SOURCES
        if options['sources_file']:
            path = Path(options['sources_file'])
            if not path.exists():
                raise CommandError(f'Arquivo não encontrado: {path}')
            sources = ast.literal_eval(path.read_text(encoding='utf-8'))

        created = 0
        updated = 0
        skipped = []

        for source in sources:
            bookmaker = find_bookmaker(user, source['brand'], source['url'])
            if bookmaker is None:
                skipped.append(f'{source["brand"]}: casa não encontrada para {source["url"]}')
                continue

            status = source.get('status') or 'confirmed'
            note = 'Confirmada' if status == 'confirmed' else f'Revisar fonte: {status}'
            _, was_created = PromotionPage.objects.update_or_create(
                bookmaker=bookmaker,
                url=source['url'],
                defaults={
                    'is_active': True,
                    'last_scan_at': timezone.now(),
                    'last_scan_note': note,
                },
            )
            created += 1 if was_created else 0
            updated += 0 if was_created else 1

        self.stdout.write(self.style.SUCCESS(f'Páginas criadas: {created}; atualizadas: {updated}.'))
        for item in skipped:
            self.stdout.write(self.style.WARNING(item))
