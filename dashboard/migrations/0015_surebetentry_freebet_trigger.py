from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0014_alter_bankrolltransaction_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='surebetentry',
            name='freebet_trigger',
            field=models.CharField(
                choices=[
                    ('won', 'Se ganhar'),
                    ('lost', 'Se perder'),
                    ('any', 'Em ambos os casos'),
                ],
                default='won',
                max_length=8,
                verbose_name='quando gera freebet',
            ),
        ),
    ]
