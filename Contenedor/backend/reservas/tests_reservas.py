from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from usuarios.signals import ROLE_CLIENTE
from vehiculos.models import EstadoVehiculo, Marca, Modelo, TipoVehiculo, Vehiculo

from .forms import ReservarVehiculoForm
from .models import EstadoReserva, FranquiciaTarjeta, MetodoPago, Pago, Reserva
from .estrategias import obtener_estrategia_pago
from .views_resevas import _crear_reserva_en_transaccion


# =====================================================================
# PRUEBA 1: METODO RESERVAS VENCIDAS
# =====================================================================
class ReservasVencidasTests(TestCase):
	def setUp(self):
		self.User = get_user_model()
		self.user = self.User.objects.create_user(
			username='cliente1',
			email='cliente1@example.com',
			dni='12345678',
			password='password123',
		)

		marca = Marca.objects.create(nombre='Toyota')
		modelo = Modelo.objects.create(nombre='Corolla', marca=marca)
		tipo_vehiculo = TipoVehiculo.objects.create(nombre='Sedan')
		estado_vehiculo = EstadoVehiculo.objects.create(nombre='Disponible')

		self.vehiculo = Vehiculo.objects.create(
			matricula='ABC123',
			precio_x_dia=100,
			activo=True,
			esta_aprobado=True,
			duenio=self.user,
			tipo_vehiculo=tipo_vehiculo,
			estado_vehiculo=estado_vehiculo,
			modelo=modelo,
		)

		self.estado_pendiente = EstadoReserva.objects.create(nombre='Pendiente')

	def _crear_reserva_pasada(self):
		hoy = timezone.localdate()
		return Reserva.objects.create(
			monto_total=200,
			fecha_inicio=hoy - timedelta(days=4),
			fecha_fin=hoy - timedelta(days=1),
			estado_reserva=self.estado_pendiente,
			cliente=self.user,
			vehiculo=self.vehiculo,
		)

	def test_mis_reservas_finaliza_automaticamente_las_vencidas(self):
		reserva = self._crear_reserva_pasada()
		self.client.force_login(self.user)

		response = self.client.get(reverse('mis_reservas'))

		self.assertEqual(response.status_code, 200)
		reserva.refresh_from_db()
		self.assertEqual(reserva.estado_reserva.nombre, 'Finalizada')

	def test_cancelar_reserva_pasada_la_marca_como_finalizada_y_no_la_cancela(self):
		reserva = self._crear_reserva_pasada()
		self.client.force_login(self.user)

		response = self.client.post(reverse('cancelar_reserva', args=[reserva.id]))

		self.assertEqual(response.status_code, 302)
		reserva.refresh_from_db()
		self.assertEqual(reserva.estado_reserva.nombre, 'Finalizada')

		mensajes = [str(message) for message in get_messages(response.wsgi_request)]
		self.assertTrue(any('ya finalizó' in mensaje for mensaje in mensajes))


# =====================================================================
# PRUEBA 2: METODO CREAR RESERVA EN TRANSACCION
# =====================================================================
class CrearReservaEnTransaccionTestCase(TestCase):
	def setUp(self):
		self.User = get_user_model()
		self.cliente = self.User.objects.create_user(
			username='cliente_transaccion',
			email='cliente_transaccion@example.com',
			dni='17171717',
			password='password123',
		)
		self.propietario = self.User.objects.create_user(
			username='propietario_transaccion',
			email='propietario_transaccion@example.com',
			dni='18181818',
			password='password123',
		)

		self.marca = Marca.objects.create(nombre='Honda')
		self.modelo = Modelo.objects.create(nombre='Civic', marca=self.marca)
		self.tipo = TipoVehiculo.objects.create(nombre='Auto')
		self.estado = EstadoVehiculo.objects.create(nombre='Excelente')

		self.vehiculo = Vehiculo.objects.create(
			matricula='HC 555 AA',
			precio_x_dia=10000.00,
			modelo=self.modelo,
			tipo_vehiculo=self.tipo,
			estado_vehiculo=self.estado,
			duenio=self.propietario,
			activo=True,
			esta_aprobado=True,
		)

		self.estado_pendiente = EstadoReserva.objects.create(nombre='Pendiente')
		self.estado_cancelada = EstadoReserva.objects.create(nombre='Cancelada')

	def test_crear_reserva_en_transaccion_camino_feliz(self):
		hoy = timezone.localdate()
		reserva, mensaje_error = _crear_reserva_en_transaccion(
			usuario=self.cliente,
			vehiculo=self.vehiculo,
			fecha_inicio=hoy + timedelta(days=2),
			fecha_fin=hoy + timedelta(days=5),
		)

		self.assertIsNone(mensaje_error)
		self.assertIsNotNone(reserva.id)
		self.assertEqual(reserva.estado_reserva.nombre, 'Pendiente')
		# Monto base: 3 días × $10000 = $30000 (sin recargo, el recargo se aplica en checkout)
		self.assertEqual(reserva.monto_total, Decimal('30000.00'))

	def test_crear_reserva_en_transaccion_rechaza_vehiculo_propio(self):
		hoy = timezone.localdate()
		vehiculo_propio = Vehiculo.objects.create(
			matricula='HP 111 BB',
			precio_x_dia=8000.00,
			modelo=self.modelo,
			tipo_vehiculo=self.tipo,
			estado_vehiculo=self.estado,
			duenio=self.cliente,
			activo=True,
			esta_aprobado=True,
		)

		reserva, mensaje_error = _crear_reserva_en_transaccion(
			usuario=self.cliente,
			vehiculo=vehiculo_propio,
			fecha_inicio=hoy + timedelta(days=2),
			fecha_fin=hoy + timedelta(days=5),
		)

		self.assertIsNone(reserva)
		self.assertEqual(mensaje_error, 'No puedes reservar un vehiculo propio.')
		self.assertEqual(Reserva.objects.count(), 0)

	def test_crear_reserva_en_transaccion_rechaza_vehiculo_inactivo(self):
		hoy = timezone.localdate()
		self.vehiculo.activo = False
		self.vehiculo.save(update_fields=['activo'])

		reserva, mensaje_error = _crear_reserva_en_transaccion(
			usuario=self.cliente,
			vehiculo=self.vehiculo,
			fecha_inicio=hoy + timedelta(days=2),
			fecha_fin=hoy + timedelta(days=5),
		)

		self.assertIsNone(reserva)
		self.assertEqual(mensaje_error, 'El vehiculo ya no esta disponible para reservar.')
		self.assertEqual(Reserva.objects.count(), 0)

	def test_crear_reserva_en_transaccion_detecta_solapamiento(self):
		hoy = timezone.localdate()
		Reserva.objects.create(
			monto_total=Decimal('20000.00'),
			fecha_inicio=hoy + timedelta(days=2),
			fecha_fin=hoy + timedelta(days=5),
			estado_reserva=self.estado_pendiente,
			cliente=self.cliente,
			vehiculo=self.vehiculo,
		)

		reserva, mensaje_error = _crear_reserva_en_transaccion(
			usuario=self.cliente,
			vehiculo=self.vehiculo,
			fecha_inicio=hoy + timedelta(days=3),
			fecha_fin=hoy + timedelta(days=6),
		)

		self.assertIsNone(reserva)
		self.assertEqual(
			mensaje_error,
			'Alguien mas reservó este vehiculo para esas fechas. Por favor, intenta con otro rango.',
		)
		self.assertEqual(Reserva.objects.count(), 1)
	
	def test_crear_reserva_en_transaccion_rechaza_vehiculo_no_aprobado(self):
		hoy = timezone.localdate()
		# Forzamos que el vehículo no esté aprobado por el administrador
		self.vehiculo.esta_aprobado = False
		self.vehiculo.save(update_fields=['esta_aprobado'])

		reserva, mensaje_error = _crear_reserva_en_transaccion(
			usuario=self.cliente,
			vehiculo=self.vehiculo,
			fecha_inicio=hoy + timedelta(days=2),
			fecha_fin=hoy + timedelta(days=5),
		)

		self.assertIsNone(reserva)
		self.assertEqual(mensaje_error, 'El vehiculo ya no esta disponible para reservar.')
		self.assertEqual(Reserva.objects.count(), 0)


# =====================================================================
# PRUEBA 3: METODO VALIDAR DATOS DE RESERVA
# =====================================================================
class ValidarDatosReservaTestCase(TestCase):
	def setUp(self):
		self.marca = Marca.objects.create(nombre='Ford')
		self.modelo = Modelo.objects.create(nombre='Fiesta', marca=self.marca)
		self.tipo = TipoVehiculo.objects.create(nombre='Auto')
		self.estado = EstadoVehiculo.objects.create(nombre='Excelente')

		self.vehiculo_activo = Vehiculo.objects.create(
			matricula='AF 123 XZ',
			precio_x_dia=10000.00,
			modelo=self.modelo,
			tipo_vehiculo=self.tipo,
			estado_vehiculo=self.estado,
			activo=True,
			esta_aprobado=True,
		)

		self.vehiculo_inactivo = Vehiculo.objects.create(
			matricula='AB 987 YZ',
			precio_x_dia=12000.00,
			modelo=self.modelo,
			tipo_vehiculo=self.tipo,
			estado_vehiculo=self.estado,
			activo=False,
			esta_aprobado=True,
		)

	def test_validar_datos_camino_feliz(self):
		hoy = timezone.localdate()
		form = ReservarVehiculoForm(data={
			'vehiculo_id': self.vehiculo_activo.id,
			'fecha_inicio': hoy + timedelta(days=2),
			'fecha_fin': hoy + timedelta(days=4),
		})

		self.assertTrue(form.is_valid())
		self.assertEqual(form.cleaned_data['vehiculo'], self.vehiculo_activo)

	def test_validar_datos_vehiculo_inactivo(self):
		hoy = timezone.localdate()
		form = ReservarVehiculoForm(data={
			'vehiculo_id': self.vehiculo_inactivo.id,
			'fecha_inicio': hoy + timedelta(days=2),
			'fecha_fin': hoy + timedelta(days=4),
		})

		self.assertFalse(form.is_valid())
		self.assertIn('vehiculo_id', form.errors)

	def test_validar_datos_rango_fechas_invalido(self):
		hoy = timezone.localdate()
		form = ReservarVehiculoForm(data={
			'vehiculo_id': self.vehiculo_activo.id,
			'fecha_inicio': hoy + timedelta(days=3),
			'fecha_fin': hoy + timedelta(days=3),
		})

		self.assertFalse(form.is_valid())
		self.assertIn('fecha_fin', form.errors)


# =====================================================================
# PRUEBA 4: METODO CREAR RESERVA
# =====================================================================
class CrearReservaViewTestCase(TestCase):
	def setUp(self):
		self.User = get_user_model()
		self.cliente = self.User.objects.create_user(
			username='cliente_reserva',
			email='cliente_reserva@example.com',
			dni='77777777',
			password='password123',
		)
		grupo_cliente, _ = Group.objects.get_or_create(name=ROLE_CLIENTE)
		self.cliente.groups.add(grupo_cliente)

		self.propietario = self.User.objects.create_user(
			username='propietario_reserva',
			email='propietario_reserva@example.com',
			dni='88888888',
			password='password123',
		)

		self.marca = Marca.objects.create(nombre='Toyota')
		self.modelo = Modelo.objects.create(nombre='Corolla', marca=self.marca)
		self.tipo = TipoVehiculo.objects.create(nombre='Sedan')
		self.estado = EstadoVehiculo.objects.create(nombre='Disponible')

		self.vehiculo = Vehiculo.objects.create(
			matricula='AC 123 CD',
			precio_x_dia=10000.00,
			modelo=self.modelo,
			tipo_vehiculo=self.tipo,
			estado_vehiculo=self.estado,
			duenio=self.propietario,
			activo=True,
			esta_aprobado=True,
		)

		self.estado_pendiente = EstadoReserva.objects.create(nombre='Pendiente')

	def test_crear_reserva_camino_feliz_redirige_al_checkout(self):
		self.client.force_login(self.cliente)
		hoy = timezone.localdate()
		respuesta = self.client.post(reverse('crear_reserva'), {
			'vehiculo_id': self.vehiculo.id,
			'fecha_inicio': str(hoy + timedelta(days=2)),
			'fecha_fin': str(hoy + timedelta(days=4)),
		})

		# Ahora redirige al checkout en vez de al inicio
		self.assertEqual(respuesta.status_code, 302)
		self.assertEqual(Reserva.objects.count(), 1)
		reserva = Reserva.objects.first()
		self.assertEqual(reserva.cliente, self.cliente)
		self.assertEqual(reserva.vehiculo, self.vehiculo)
		self.assertEqual(reserva.estado_reserva.nombre, 'Pendiente')
		self.assertIn(f'/reservas/checkout/{reserva.id}/', respuesta.url)

	def test_crear_reserva_usuario_sin_rol_devuelve_403(self):
		usuario = self.User.objects.create_user(
			username='sin_rol',
			email='sin_rol@example.com',
			dni='99999999',
			password='password123',
		)
		self.client.force_login(usuario)
		hoy = timezone.localdate()
		respuesta = self.client.post(reverse('crear_reserva'), {
			'vehiculo_id': self.vehiculo.id,
			'fecha_inicio': str(hoy + timedelta(days=2)),
			'fecha_fin': str(hoy + timedelta(days=4)),
		})

		self.assertEqual(respuesta.status_code, 403)
		self.assertEqual(Reserva.objects.count(), 0)

	def test_crear_reserva_con_fechas_solapadas_devuelve_400(self):
		self.client.force_login(self.cliente)
		hoy = timezone.localdate()
		Reserva.objects.create(
			monto_total=Decimal('20000.00'),
			fecha_inicio=hoy + timedelta(days=2),
			fecha_fin=hoy + timedelta(days=4),
			estado_reserva=self.estado_pendiente,
			cliente=self.cliente,
			vehiculo=self.vehiculo,
		)

		respuesta = self.client.post(reverse('crear_reserva'), {
			'vehiculo_id': self.vehiculo.id,
			'fecha_inicio': str(hoy + timedelta(days=3)),
			'fecha_fin': str(hoy + timedelta(days=5)),
		})

		self.assertEqual(respuesta.status_code, 400)
		self.assertEqual(Reserva.objects.count(), 1)


# =====================================================================
# PRUEBA 5: METODO CANCELAR RESERVA
# =====================================================================
class CancelarReservaViewTestCase(TestCase):
	def setUp(self):
		self.User = get_user_model()
		self.cliente = self.User.objects.create_user(
			username='cliente_cancelar',
			email='cliente_cancelar@example.com',
			dni='12121212',
			password='password123',
		)
		grupo_cliente, _ = Group.objects.get_or_create(name=ROLE_CLIENTE)
		self.cliente.groups.add(grupo_cliente)

		self.propietario = self.User.objects.create_user(
			username='propietario_cancelar',
			email='propietario_cancelar@example.com',
			dni='13131313',
			password='password123',
		)

		self.marca = Marca.objects.create(nombre='Nissan')
		self.modelo = Modelo.objects.create(nombre='Versa', marca=self.marca)
		self.tipo = TipoVehiculo.objects.create(nombre='Auto')
		self.estado_vehiculo = EstadoVehiculo.objects.create(nombre='Disponible')
		self.estado_pendiente = EstadoReserva.objects.create(nombre='Pendiente')
		self.estado_cancelada = EstadoReserva.objects.create(nombre='Cancelada')

		self.vehiculo = Vehiculo.objects.create(
			matricula='AA 999 ZZ',
			precio_x_dia=30000.00,
			modelo=self.modelo,
			tipo_vehiculo=self.tipo,
			estado_vehiculo=self.estado_vehiculo,
			duenio=self.propietario,
			activo=True,
			esta_aprobado=True,
		)

	def test_cancelar_reserva_camino_feliz(self):
		self.client.force_login(self.cliente)
		hoy = timezone.localdate()
		reserva = Reserva.objects.create(
			monto_total=Decimal('60000.00'),
			fecha_inicio=hoy + timedelta(days=3),
			fecha_fin=hoy + timedelta(days=5),
			estado_reserva=self.estado_pendiente,
			cliente=self.cliente,
			vehiculo=self.vehiculo,
		)

		respuesta = self.client.post(reverse('cancelar_reserva', args=[reserva.id]))

		self.assertEqual(respuesta.status_code, 302)
		reserva.refresh_from_db()
		self.assertEqual(reserva.estado_reserva.nombre, 'Cancelada')
		mensajes = [str(message) for message in get_messages(respuesta.wsgi_request)]
		self.assertTrue(any('cancelada correctamente' in mensaje for mensaje in mensajes))


# =====================================================================
# PRUEBA 6: METODO MOSTRAR RESERVAS DEL USUARIO
# =====================================================================
class ObtenerReservasUsuarioTestCase(TestCase):
	def setUp(self):
		self.User = get_user_model()
		self.cliente = self.User.objects.create_user(
			username='cliente_lista',
			email='cliente_lista@example.com',
			dni='14141414',
			password='password123',
		)
		grupo_cliente, _ = Group.objects.get_or_create(name=ROLE_CLIENTE)
		self.cliente.groups.add(grupo_cliente)

		self.propietario = self.User.objects.create_user(
			username='propietario_lista',
			email='propietario_lista@example.com',
			dni='15151515',
			password='password123',
		)

		self.marca = Marca.objects.create(nombre='Renault')
		self.modelo = Modelo.objects.create(nombre='Sandero', marca=self.marca)
		self.tipo = TipoVehiculo.objects.create(nombre='Auto')
		self.estado_vehiculo = EstadoVehiculo.objects.create(nombre='Bueno')
		self.estado_pendiente = EstadoReserva.objects.create(nombre='Pendiente')
		self.estado_finalizada = EstadoReserva.objects.create(nombre='Finalizada')

		self.vehiculo = Vehiculo.objects.create(
			matricula='BB 222 BB',
			precio_x_dia=12000.00,
			modelo=self.modelo,
			tipo_vehiculo=self.tipo,
			estado_vehiculo=self.estado_vehiculo,
			duenio=self.propietario,
			activo=True,
			esta_aprobado=True,
		)

	def test_obtener_reservas_usuario_separa_activos_y_historial(self):
		self.client.force_login(self.cliente)
		hoy = timezone.localdate()

		reserva_activa = Reserva.objects.create(
			monto_total=Decimal('24000.00'),
			fecha_inicio=hoy + timedelta(days=2),
			fecha_fin=hoy + timedelta(days=4),
			estado_reserva=self.estado_pendiente,
			cliente=self.cliente,
			vehiculo=self.vehiculo,
		)
		reserva_historial = Reserva.objects.create(
			monto_total=Decimal('12000.00'),
			fecha_inicio=hoy - timedelta(days=5),
			fecha_fin=hoy - timedelta(days=2),
			estado_reserva=self.estado_finalizada,
			cliente=self.cliente,
			vehiculo=self.vehiculo,
		)

		respuesta = self.client.get(reverse('mis_reservas'))

		self.assertEqual(respuesta.status_code, 200)
		self.assertIn(reserva_activa, respuesta.context['activos'])
		self.assertIn(reserva_historial, respuesta.context['historial'])


# =====================================================================
# PRUEBA 7: CHECKOUT Y PAGO
# =====================================================================
class CheckoutTestCase(TestCase):
	def setUp(self):
		self.User = get_user_model()
		self.cliente = self.User.objects.create_user(
			username='cliente_checkout',
			email='cliente_checkout@example.com',
			dni='20202020',
			password='password123',
		)
		grupo_cliente, _ = Group.objects.get_or_create(name=ROLE_CLIENTE)
		self.cliente.groups.add(grupo_cliente)

		self.propietario = self.User.objects.create_user(
			username='propietario_checkout',
			email='propietario_checkout@example.com',
			dni='21212121',
			password='password123',
		)

		self.marca = Marca.objects.create(nombre='Chevrolet')
		self.modelo = Modelo.objects.create(nombre='Onix', marca=self.marca)
		self.tipo = TipoVehiculo.objects.create(nombre='Auto')
		self.estado_vehiculo = EstadoVehiculo.objects.create(nombre='Disponible')
		self.estado_pendiente = EstadoReserva.objects.create(nombre='Pendiente')
		self.estado_confirmada = EstadoReserva.objects.create(nombre='Confirmada')
		self.estado_cancelada = EstadoReserva.objects.create(nombre='Cancelada')

		self.vehiculo = Vehiculo.objects.create(
			matricula='CC 333 CC',
			precio_x_dia=15000.00,
			modelo=self.modelo,
			tipo_vehiculo=self.tipo,
			estado_vehiculo=self.estado_vehiculo,
			duenio=self.propietario,
			activo=True,
			esta_aprobado=True,
		)

		self.metodo_credito = MetodoPago.objects.create(nombre='Tarjeta de crédito')
		self.metodo_transferencia = MetodoPago.objects.create(nombre='Transferencia')
		self.franquicia_visa, _ = FranquiciaTarjeta.objects.get_or_create(nombre='Visa', defaults={'tipo': 'ambas'})

		hoy = timezone.localdate()
		self.reserva = Reserva.objects.create(
			monto_total=Decimal('30000.00'),
			fecha_inicio=hoy + timedelta(days=3),
			fecha_fin=hoy + timedelta(days=5),
			estado_reserva=self.estado_pendiente,
			cliente=self.cliente,
			vehiculo=self.vehiculo,
		)

	def test_checkout_view_get_renderiza_correctamente(self):
		self.client.force_login(self.cliente)
		respuesta = self.client.get(reverse('checkout', args=[self.reserva.id]))

		self.assertEqual(respuesta.status_code, 200)
		self.assertContains(respuesta, 'Checkout de Pago')
		# El monto puede renderizarse con coma (localización) o punto
		contenido = respuesta.content.decode('utf-8')
		self.assertTrue('30000' in contenido)

	def test_checkout_reserva_confirmada_redirige(self):
		self.client.force_login(self.cliente)
		self.reserva.estado_reserva = self.estado_confirmada
		self.reserva.save()

		respuesta = self.client.get(reverse('checkout', args=[self.reserva.id]))
		self.assertEqual(respuesta.status_code, 302)

	def test_cancelar_checkout_cancela_reserva(self):
		self.client.force_login(self.cliente)
		respuesta = self.client.post(reverse('cancelar_checkout', args=[self.reserva.id]))

		self.assertEqual(respuesta.status_code, 302)
		self.reserva.refresh_from_db()
		self.assertEqual(self.reserva.estado_reserva.nombre, 'Cancelada')

	def test_checkout_exitoso_muestra_comprobante(self):
		self.client.force_login(self.cliente)
		# Crear un pago para la reserva
		Pago.objects.create(
			reserva=self.reserva,
			metodo_pago=self.metodo_credito,
			comprobante_transaccion='TRX-CC-TEST-12345',
			monto=Decimal('33000.00'),
			franquicia=self.franquicia_visa,
			nombre_titular='Juan Test',
			ultimos_4_digitos='1234',
		)
		self.reserva.estado_reserva = self.estado_confirmada
		self.reserva.save()

		respuesta = self.client.get(reverse('checkout_exitoso', args=[self.reserva.id]))
		self.assertEqual(respuesta.status_code, 200)
		self.assertContains(respuesta, 'TRX-CC-TEST-12345')
		self.assertContains(respuesta, 'Pago exitoso')


# =====================================================================
# PRUEBA 8: ESTRATEGIAS ENRIQUECIDAS
# =====================================================================
class EstrategiasEnriquecidasTestCase(TestCase):
	def test_estrategia_credito_calcular_total_con_recargo(self):
		estrategia = obtener_estrategia_pago('Tarjeta de crédito')
		total = estrategia.calcular_total(Decimal('10000.00'))
		self.assertEqual(total, Decimal('11000.00'))

	def test_estrategia_debito_sin_recargo(self):
		estrategia = obtener_estrategia_pago('Tarjeta de débito')
		total = estrategia.calcular_total(Decimal('10000.00'))
		self.assertEqual(total, Decimal('10000.00'))

	def test_estrategia_transferencia_con_descuento(self):
		estrategia = obtener_estrategia_pago('Transferencia')
		total = estrategia.calcular_total(Decimal('10000.00'))
		self.assertEqual(total, Decimal('9500.00'))

	def test_estrategia_credito_validar_datos_incompletos(self):
		estrategia = obtener_estrategia_pago('Tarjeta de crédito')
		resultado = estrategia.validar_datos({})
		self.assertFalse(resultado['valido'])
		self.assertTrue(len(resultado['errores']) > 0)

	def test_estrategia_credito_validar_datos_correctos(self):
		estrategia = obtener_estrategia_pago('Tarjeta de crédito')
		# 4532015112830366 es un número válido según Luhn
		resultado = estrategia.validar_datos({
			'numero_tarjeta': '4532015112830366',
			'nombre_titular': 'Juan Pérez',
			'vencimiento_mes': '12',
			'vencimiento_anio': '2028',
			'codigo_seguridad': '123',
			'franquicia_id': 1,
		})
		self.assertTrue(resultado['valido'])

	def test_estrategia_transferencia_validar_datos_correctos(self):
		estrategia = obtener_estrategia_pago('Transferencia')
		resultado = estrategia.validar_datos({
			'cbu_cvu': '0000000000000000000000',
			'titular_cuenta': 'María López',
		})
		self.assertTrue(resultado['valido'])

	def test_estrategia_transferencia_validar_cbu_invalido(self):
		estrategia = obtener_estrategia_pago('Transferencia')
		resultado = estrategia.validar_datos({
			'cbu_cvu': '12345',
			'titular_cuenta': 'María López',
		})
		self.assertFalse(resultado['valido'])
		self.assertTrue(any('CBU' in e for e in resultado['errores']))

	def test_obtener_estrategia_invalida_lanza_error(self):
		with self.assertRaises(ValueError):
			obtener_estrategia_pago('Efectivo')

	def test_estrategia_credito_obtener_campos_requeridos(self):
		estrategia = obtener_estrategia_pago('Tarjeta de crédito')
		campos = estrategia.obtener_campos_requeridos()
		nombres_campos = [c['nombre'] for c in campos]
		self.assertIn('numero_tarjeta', nombres_campos)
		self.assertIn('nombre_titular', nombres_campos)
		self.assertIn('codigo_seguridad', nombres_campos)
		self.assertIn('franquicia_id', nombres_campos)
		self.assertIn('vencimiento_mes', nombres_campos)
		self.assertIn('vencimiento_anio', nombres_campos)

	def test_estrategia_debito_obtener_campos_requeridos(self):
		estrategia = obtener_estrategia_pago('Tarjeta de débito')
		campos = estrategia.obtener_campos_requeridos()
		nombres_campos = [c['nombre'] for c in campos]
		self.assertIn('numero_tarjeta', nombres_campos)
		self.assertIn('nombre_titular', nombres_campos)
		self.assertIn('codigo_seguridad', nombres_campos)
		self.assertIn('franquicia_id', nombres_campos)
		self.assertNotIn('vencimiento_mes', nombres_campos)

	def test_estrategia_transferencia_obtener_campos_requeridos(self):
		estrategia = obtener_estrategia_pago('Transferencia')
		campos = estrategia.obtener_campos_requeridos()
		nombres_campos = [c['nombre'] for c in campos]
		self.assertIn('cbu_cvu', nombres_campos)
		self.assertIn('titular_cuenta', nombres_campos)
		self.assertIn('alias', nombres_campos)
