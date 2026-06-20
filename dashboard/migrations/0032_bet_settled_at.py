from django.db import migrations
from django.db import models


def populate_settled_at(apps, schema_editor):
    Bet = apps.get_model('dashboard', 'Bet')
    Bet.objects.exclude(status='open').filter(settled_at__isnull=True).update(
        settled_at=models.F('created_at')
    )


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0031_bet_odds_boost'),
    ]

    operations = [
        migrations.AddField(
            model_name='bet',
            name='settled_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='finalizada em'),
        ),
        migrations.RunPython(populate_settled_at, migrations.RunPython.noop),
    ]
