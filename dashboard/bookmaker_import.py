import csv
import re
import unicodedata

from django.utils import timezone

from .models import BookmakerAlias
from .models import RegulatedBookmaker


STATUS_MAP = {
    'autorizada_spa': RegulatedBookmaker.Status.AUTHORIZED,
    'autorizada': RegulatedBookmaker.Status.AUTHORIZED,
    'authorized': RegulatedBookmaker.Status.AUTHORIZED,
    'estadual': RegulatedBookmaker.Status.STATE,
    'state': RegulatedBookmaker.Status.STATE,
    'alerta_judicial': RegulatedBookmaker.Status.JUDICIAL_ALERT,
    'judicial_alert': RegulatedBookmaker.Status.JUDICIAL_ALERT,
    'inativa': RegulatedBookmaker.Status.INACTIVE,
    'inactive': RegulatedBookmaker.Status.INACTIVE,
}


def normalize_status(value):
    key = (value or '').strip().lower()
    return STATUS_MAP.get(key, RegulatedBookmaker.Status.AUTHORIZED)


def normalize_domain(value):
    return (value or '').strip().lower().replace('https://', '').replace('http://', '').strip('/')


def slug_alias(value):
    normalized = unicodedata.normalize('NFKD', value or '')
    ascii_text = normalized.encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^a-z0-9]+', '_', ascii_text.lower()).strip('_')


def alias_candidates(brand, domain):
    candidates = []
    brand = (brand or '').strip()
    if brand:
        candidates.append(brand)
        lower_brand = brand.lower()
        if lower_brand != brand:
            candidates.append(lower_brand)
        slug = slug_alias(brand)
        if slug and slug not in candidates:
            candidates.append(slug)
    domain_root = normalize_domain(domain).split('.')[0]
    if domain_root and domain_root not in candidates:
        candidates.append(domain_root)
    return list(dict.fromkeys(candidate for candidate in candidates if candidate))


def import_regulated_csv(file_obj, user, provider='the_odds_api', create_aliases=True):
    decoded = (line.decode('utf-8-sig') if isinstance(line, bytes) else line for line in file_obj)
    reader = csv.DictReader(decoded, delimiter=';')
    imported = 0
    updated = 0
    aliases_created = 0
    errors = []

    for line_number, row in enumerate(reader, start=2):
        company_name = (row.get('empresa') or '').strip()
        cnpj = (row.get('cnpj') or '').strip()
        brand = (row.get('marca') or '').strip()
        domain = normalize_domain(row.get('dominio'))
        status = normalize_status(row.get('status'))

        if not brand or not domain:
            errors.append(f'Linha {line_number}: marca e domínio são obrigatórios.')
            continue

        bookmaker, created = RegulatedBookmaker.objects.update_or_create(
            owner=user,
            domain=domain,
            defaults={
                'company_name': company_name or brand,
                'cnpj': cnpj,
                'brand': brand,
                'status': status,
                'source': 'SPA/MF CSV',
                'judicial_alert': status == RegulatedBookmaker.Status.JUDICIAL_ALERT,
                'last_checked_at': timezone.now(),
            },
        )
        imported += 1 if created else 0
        updated += 0 if created else 1

        if create_aliases:
            for alias in alias_candidates(brand, domain):
                _, alias_created = BookmakerAlias.objects.get_or_create(
                    bookmaker=bookmaker,
                    provider=provider,
                    alias=alias,
                    defaults={'provider_key': slug_alias(alias)},
                )
                aliases_created += 1 if alias_created else 0

    return {
        'imported': imported,
        'updated': updated,
        'aliases_created': aliases_created,
        'errors': errors,
    }
