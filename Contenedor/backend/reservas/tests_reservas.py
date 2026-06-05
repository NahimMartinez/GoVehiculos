from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from vehiculos.models import EstadoVehiculo, Marca, Modelo, TipoVehiculo, Vehiculo

from .models import EstadoReserva, Reserva


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
