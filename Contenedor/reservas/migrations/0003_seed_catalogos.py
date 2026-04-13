from django.db import migrations


def seed_catalogos(apps, schema_editor):
    EstadoReserva = apps.get_model('reservas', 'EstadoReserva')
    MetodoPago = apps.get_model('reservas', 'MetodoPago')

    for nombre_estado in ('Pendiente', 'Confirmada', 'Cancelada'):
        EstadoReserva.objects.get_or_create(nombre=nombre_estado)

    for nombre_metodo in ('Tarjeta de credito', 'Tarjeta de debito', 'Transferencia', 'Efectivo'):
        MetodoPago.objects.get_or_create(nombre=nombre_metodo)


class Migration(migrations.Migration):

    dependencies = [
        ('reservas', '0002_initial'),
    ]

    operations = [
        migrations.RunPython(seed_catalogos, migrations.RunPython.noop),
    ]
