from django.db import connection

def procedure_actualizar_estado_reserva(reserva_id, nuevo_estado_id):
    """Ejecuta un UPDATE directo en la base de datos saltándose el ORM."""
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE reservas_reserva SET estado_reserva_id = %s WHERE id = %s",
            [nuevo_estado_id, reserva_id]
        )


def procedure_obtener_vehiculos_disponibles():
    """Ejecuta un SELECT directo en la base de datos."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, matricula, precio_x_dia FROM vehiculos_vehiculo WHERE activo = 1 AND esta_aprobado = 1"
        )
        # Retorna los resultados como una lista de tuplas
        return cursor.fetchall()