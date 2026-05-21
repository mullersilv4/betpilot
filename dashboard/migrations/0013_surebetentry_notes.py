from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0012_bet_away_team_bet_external_event_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='surebetentry',
            name='notes',
            field=models.CharField(blank=True, max_length=180, verbose_name='observacao'),
        ),
    ]
