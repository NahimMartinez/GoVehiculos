from django.db import connection

def procedure_actualizar_estado_reserva(reserva_id, nuevo_estado_id):
    """Ejecuta un UPDATE directo en la base de datos saltándose el ORM."""
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE reservas_reserva SET estado_reserva_id = %s WHERE id = %s",
            [nuevo_estado_id, reserva_id]
        )


def procedure_obtener_vehiculos_destacados():
    """
    Ejecuta un SELECT con JOINs
    para obtener los 6 vehículos más populares con todos sus datos relacionales.
    """
    with connection.cursor() as cursor:
        cursor.execute('''
            SELECT 
                v.id, 
                v.imagen, 
                ma.nombre || ' - ' || m.nombre AS modelo,
                e.nombre AS estado_vehiculo, 
                COUNT(r.id) AS num_reservas, 
                v.precio_x_dia, 
                t.nombre AS tipo_vehiculo, 
                v.matricula
            FROM vehiculos_vehiculo v
            INNER JOIN vehiculos_modelo m ON v.modelo_id = m.id
            INNER JOIN vehiculos_marca ma ON m.marca_id = ma.id -- <-- NUEVO JOIN PARA LA MARCA
            INNER JOIN vehiculos_estadovehiculo e ON v.estado_vehiculo_id = e.id
            INNER JOIN vehiculos_tipovehiculo t ON v.tipo_vehiculo_id = t.id
            LEFT JOIN reservas_reserva r ON r.vehiculo_id = v.id
            WHERE v.activo = 1 AND v.esta_aprobado = 1
            GROUP BY v.id, v.imagen, ma.nombre, m.nombre, e.nombre, v.precio_x_dia, t.nombre, v.matricula
            ORDER BY num_reservas DESC
            LIMIT 6
        ''')
        return cursor.fetchall()