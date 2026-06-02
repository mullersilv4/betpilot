from django.db import migrations


def forwards(apps, schema_editor):
    Bet = apps.get_model('dashboard', 'Bet')
    Bet.objects.filter(strategy='Surebet').update(strategy='Proteção')

    for bet in Bet.objects.filter(market__startswith='Surebet:').iterator():
        bet.market = bet.market.replace('Surebet:', 'Proteção:', 1)
        bet.save(update_fields=['market'])

    for bet in Bet.objects.filter(notes__contains='Surebet').iterator():
        bet.notes = bet.notes.replace(
            'Surebet cadastrada com proteções:',
            'Proteção cadastrada:',
        ).replace('Surebet', 'Proteção')
        bet.save(update_fields=['notes'])


def backwards(apps, schema_editor):
    Bet = apps.get_model('dashboard', 'Bet')
    Bet.objects.filter(strategy='Proteção').update(strategy='Surebet')

    for bet in Bet.objects.filter(market__startswith='Proteção:').iterator():
        bet.market = bet.market.replace('Proteção:', 'Surebet:', 1)
        bet.save(update_fields=['market'])

    for bet in Bet.objects.filter(notes__contains='Proteção').iterator():
        bet.notes = bet.notes.replace(
            'Proteção cadastrada:',
            'Surebet cadastrada com proteções:',
        ).replace('Proteção', 'Surebet')
        bet.save(update_fields=['notes'])


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0025_freebet_extraction_bet'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
