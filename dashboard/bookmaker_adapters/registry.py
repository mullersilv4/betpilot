from .base import PlaceholderBookmakerAdapter
from .base import PublicWebBookmakerAdapter


class BetanoAdapter(PublicWebBookmakerAdapter):
    bookmaker = 'betano'
    display_name = 'Betano'
    base_url = 'https://betano.bet.br/'
    search_paths = (
        '/search/?query={query}',
        '/busca/?query={query}',
        '/sport/futebol/',
    )


class SuperbetAdapter(PublicWebBookmakerAdapter):
    bookmaker = 'superbet'
    display_name = 'Superbet'
    base_url = 'https://superbet.bet.br/'
    search_paths = (
        '/pesquisa?query={query}',
        '/search?query={query}',
        '/esportes/futebol',
    )


class Bet365Adapter(PublicWebBookmakerAdapter):
    bookmaker = 'bet365'
    display_name = 'Bet365'
    base_url = 'https://bet365.bet.br/'
    search_paths = (
        '/#/AS/B1/?search={query}',
        '/#/HO/',
    )


class NovibetAdapter(PublicWebBookmakerAdapter):
    bookmaker = 'novibet'
    display_name = 'Novibet'
    base_url = 'https://novibet.bet.br/'
    search_paths = (
        '/apostas-esportivas/pesquisa?q={query}',
        '/sports/search?q={query}',
        '/apostas-esportivas/futebol',
    )


class BetfairAdapter(PlaceholderBookmakerAdapter):
    bookmaker = 'betfair'
    display_name = 'Betfair'


class EstrelaBetAdapter(PlaceholderBookmakerAdapter):
    bookmaker = 'estrelabet'
    display_name = 'EstrelaBet'


class EsportesDaSorteAdapter(PlaceholderBookmakerAdapter):
    bookmaker = 'esportesdasorte'
    display_name = 'Esportes da Sorte'


ADAPTERS = {
    adapter.bookmaker: adapter
    for adapter in (
        BetanoAdapter,
        SuperbetAdapter,
        Bet365Adapter,
        NovibetAdapter,
        BetfairAdapter,
        EstrelaBetAdapter,
        EsportesDaSorteAdapter,
    )
}


def get_adapter(bookmaker):
    adapter_class = ADAPTERS.get(bookmaker)
    return adapter_class() if adapter_class else None


def iter_adapters(bookmakers=None):
    keys = bookmakers or ADAPTERS.keys()
    for bookmaker in keys:
        adapter = get_adapter(bookmaker)
        if adapter:
            yield adapter
