from django.db import migrations
from django.db import models
import django.db.models.deletion


def move_goals_to_entities(apps, schema_editor):
    MonthlyGoal = apps.get_model('dashboard', 'MonthlyGoal')
    Entity = apps.get_model('dashboard', 'Entity')

    for goal in MonthlyGoal.objects.select_related('bankroll', 'bankroll__entity').all():
        bankroll = goal.bankroll
        entity = bankroll.entity if bankroll else None
        if entity is None and bankroll and bankroll.owner_id:
            entity, _created = Entity.objects.get_or_create(
                owner_id=bankroll.owner_id,
                name='Sem entidade',
                defaults={'notes': 'Criada automaticamente para migrar metas antigas.'},
            )
        if entity is None:
            goal.delete()
            continue
        goal.entity_id = entity.pk
        goal.save(update_fields=['entity'])

    seen = set()
    for goal in MonthlyGoal.objects.order_by('entity_id', 'month', 'id'):
        key = (goal.entity_id, goal.month)
        if key in seen:
            goal.delete()
        else:
            seen.add(key)


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0021_bankrolltransaction_bet_surebetentry_bankroll_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='monthlygoal',
            name='entity',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='goals',
                to='dashboard.entity',
                verbose_name='entidade',
            ),
        ),
        migrations.RunPython(move_goals_to_entities, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name='monthlygoal',
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name='monthlygoal',
            name='bankroll',
        ),
        migrations.AlterField(
            model_name='monthlygoal',
            name='entity',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='goals',
                to='dashboard.entity',
                verbose_name='entidade',
            ),
        ),
        migrations.AlterModelOptions(
            name='monthlygoal',
            options={
                'ordering': ['-month', 'entity__name'],
                'verbose_name': 'meta mensal',
                'verbose_name_plural': 'metas mensais',
            },
        ),
        migrations.AlterUniqueTogether(
            name='monthlygoal',
            unique_together={('entity', 'month')},
        ),
    ]
