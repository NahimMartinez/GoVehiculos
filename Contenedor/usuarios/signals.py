from django.apps import apps
from django.contrib.auth.models import Group, Permission
from django.db.models.signals import post_migrate
from django.dispatch import receiver

# Roles de usuario que se utilizarán en la aplicación para asignar permisos específicos a cada grupo. Estos roles se utilizan para diferenciar entre los clientes, que pueden hacer reservas, y los socios, que pueden gestionar vehículos y ver su propia flota.
ROLE_CLIENTE = "Clientes"
ROLE_SOCIO = "Socios"

# Esta función se ejecuta después de que se hayan aplicado las migraciones a la base de datos. Su función es asegurarse de que existan los grupos "Clientes" y "Socios", y que cada grupo tenga los permisos adecuados asignados. Esto es crucial para el correcto funcionamiento de la aplicación, ya que los permisos determinan qué acciones pueden realizar los usuarios según su rol.
@receiver(post_migrate)
def ensure_groups_and_permissions(sender, **kwargs):
    vehiculo_model = apps.get_model("vehiculos", "Vehiculo")
    reserva_model = apps.get_model("reservas", "Reserva")

    required_permissions = [
        (vehiculo_model, "view_vehiculo"),
        (vehiculo_model, "add_vehiculo"),
        (vehiculo_model, "change_vehiculo"),
        (vehiculo_model, "delete_vehiculo"),
        (vehiculo_model, "view_own_fleet"),
        (reserva_model, "add_reserva"),
        (reserva_model, "view_reserva"),
        (reserva_model, "delete_reserva"),
    ]

    permissions = []
    # El for hace lo siguiente por cada permiso requerido: intenta obtener el permiso de la base de datos utilizando su content type (que se basa en el modelo al que pertenece) y su codename (que es el nombre del permiso). Si el permiso no existe, simplemente lo omite. Esto asegura que solo se asignen permisos válidos a los grupos, y que la función pueda ejecutarse sin errores incluso si algunos permisos aún no han sido creados por las migraciones. Por ejemplo: [(Vehiculo, "view_vehiculo"), (Reserva, "add_reserva"), etc.]
    for model, codename in required_permissions:
        try:
            permissions.append(Permission.objects.get(content_type__app_label=model._meta.app_label, codename=codename))
        except Permission.DoesNotExist:
            return

    group_cliente, _ = Group.objects.get_or_create(name=ROLE_CLIENTE)
    group_socio, _ = Group.objects.get_or_create(name=ROLE_SOCIO)
    # Los permisos del cliente incluyen ver vehículos, agregar reservas, ver reservas y eliminar reservas, lo que les permite interactuar con la plataforma para alquilar vehículos sin tener acceso a la gestión de los mismos.
    permisos_cliente = [
        perm
        for perm in permissions
        if perm.codename in {"view_vehiculo", "add_reserva", "view_reserva", "delete_reserva"}
    ]
    # Los permisos del socio incluyen todos los permisos del cliente más los permisos para gestionar vehículos y ver su propia flota, lo que les permite tener un control total sobre sus vehículos y reservas.
    permisos_socio = [
        perm
        for perm in permissions
        if perm.codename
        in {"add_vehiculo", "change_vehiculo", "delete_vehiculo", "view_vehiculo", "view_own_fleet"} # view_own_fleet es un permiso personalizado que permite a los socios ver solo su propia flota de vehículos, lo que es esencial para la gestión de sus vehículos sin interferir con los vehículos de otros socios.
    ]
    # Cada vez que se ejecuta esta función, se asegura de que los grupos "Clientes" y "Socios" existan, y luego asigna los permisos correspondientes a cada grupo. Esto garantiza que los permisos estén siempre actualizados después de migrar la base de datos, lo que es crucial para el correcto funcionamiento de la aplicación. Nos aseguramos que tras cada migración existan los grupos y permisos necesarios para que los usuarios puedan realizar las acciones correspondientes a su rol sin problemas de autorización.
    group_cliente.permissions.add(*permisos_cliente)
    group_socio.permissions.add(*permisos_socio)
