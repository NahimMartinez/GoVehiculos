import django.db.models.deletion
from django.db import migrations, models


def dedupe_catalogs_and_payments(apps, schema_editor):
    EstadoReserva = apps.get_model('reservas', 'EstadoReserva')
    MetodoPago = apps.get_model('reservas', 'MetodoPago')
    Reserva = apps.get_model('reservas', 'Reserva')
    Pago = apps.get_model('reservas', 'Pago')

    for nombre in EstadoReserva.objects.values_list('nombre', flat=True).distinct():
        estados = EstadoReserva.objects.filter(nombre=nombre).order_by('id')
        estado_principal = estados.first()
        if not estado_principal:
            continue

        for estado_duplicado in estados.exclude(id=estado_principal.id):
            Reserva.objects.filter(estado_reserva_id=estado_duplicado.id).update(
                estado_reserva_id=estado_principal.id
            )
            estado_duplicado.delete()

    for nombre in MetodoPago.objects.values_list('nombre', flat=True).distinct():
        metodos = MetodoPago.objects.filter(nombre=nombre).order_by('id')
        metodo_principal = metodos.first()
        if not metodo_principal:
            continue

        for metodo_duplicado in metodos.exclude(id=metodo_principal.id):
            Pago.objects.filter(metodo_pago_id=metodo_duplicado.id).update(
                metodo_pago_id=metodo_principal.id
            )
            metodo_duplicado.delete()

    for reserva_id in Pago.objects.exclude(reserva_id=None).values_list('reserva_id', flat=True).distinct():
        pagos = Pago.objects.filter(reserva_id=reserva_id).order_by('id')
        pago_principal = pagos.first()
        if not pago_principal:
            continue

        pagos.exclude(id=pago_principal.id).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('reservas', '0003_seed_catalogos'),
    ]

    operations = [
        migrations.RunPython(dedupe_catalogs_and_payments, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='estadoreserva',
            name='nombre',
            field=models.CharField(max_length=25, unique=True),
        ),
        migrations.AlterField(
            model_name='metodopago',
            name='nombre',
            field=models.CharField(max_length=30, unique=True),
        ),
        migrations.AlterField(
            model_name='pago',
            name='reserva',
            field=models.OneToOneField(null=True, on_delete=django.db.models.deletion.SET_NULL, to='reservas.reserva'),
        ),
    ]
