from django.db import migrations, models


def set_vehiculos_aprobados(apps, schema_editor):
    Vehiculo = apps.get_model('vehiculos', 'Vehiculo')
    Vehiculo.objects.all().update(esta_aprobado=True)


class Migration(migrations.Migration):

    dependencies = [
        ('vehiculos', '0002_vehiculo_activo_alter_vehiculo_matricula_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='vehiculo',
            name='esta_aprobado',
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(set_vehiculos_aprobados, migrations.RunPython.noop),
    ]
