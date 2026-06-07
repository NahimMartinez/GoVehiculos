from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .estrategias import obtener_estrategia_pago
from vehiculos.models import Vehiculo


class ReservarVehiculoForm(forms.Form):
	"""Formulario de creación de reserva. Ya no incluye método de pago — eso se elige en el checkout."""
	vehiculo_id = forms.IntegerField(min_value=1)
	fecha_inicio = forms.DateField()
	fecha_fin = forms.DateField()

	MAX_DIAS_RESERVA = 30 # Limite máximo de días para una reserva, lo que ayuda a controlar la duración de las reservas y evitar bloqueos prolongados de vehículos.
	MIN_DIAS_ANTELACION = 2 # La fecha de inicio debe ser al menos 2 días (48 horas) a partir de hoy. Si hoy es día 1, la fecha más próxima posible es el día 3.
	MIN_DIAS_RESERVA = 1 # Duración mínima de una reserva: al menos 1 día (24 horas).

	def clean_vehiculo_id(self):
		"""
		Valida que el ID del vehículo proporcionado corresponde a un vehículo activo y aprobado.
		Si el vehículo no existe o no cumple con estas condiciones, se lanza una ValidationError, 
		lo que garantiza que solo se puedan reservar vehículos disponibles para los clientes.
		"""
		vehiculo_id = self.cleaned_data['vehiculo_id']

		try:
			vehiculo = Vehiculo.objects.get(id=vehiculo_id, activo=True, esta_aprobado=True)
		except Vehiculo.DoesNotExist as exc:
			raise ValidationError('El vehiculo no esta disponible para reservar.') from exc

		self.cleaned_data['vehiculo'] = vehiculo
		return vehiculo_id

	def clean(self):
		"""
		Valida las fechas de inicio y fin de la reserva.
		Verifica que:
		- La fecha de inicio no esté en el pasado (comparando solo fechas sin considerar horas/minutos).
		- La fecha de inicio tenga al menos MIN_DIAS_ANTELACION días de antelación.
		- La fecha de fin sea estrictamente posterior a la fecha de inicio.
		- La duración total sea de al menos MIN_DIAS_RESERVA día(s).
		- La duración total de la reserva no supere el límite máximo (MAX_DIAS_RESERVA).
		"""
		cleaned_data = super().clean()
		fecha_inicio = cleaned_data.get('fecha_inicio')
		fecha_fin = cleaned_data.get('fecha_fin')

		if not fecha_inicio or not fecha_fin:
			return cleaned_data

		hoy = timezone.localdate()
		if fecha_inicio < hoy:
			self.add_error('fecha_inicio', 'La fecha de inicio no puede estar en el pasado.')

		# Antelación mínima de 48 horas (2 días). Si hoy es 1, fecha mínima es 3.
		fecha_minima = hoy + timezone.timedelta(days=self.MIN_DIAS_ANTELACION)
		if fecha_inicio < fecha_minima:
			self.add_error(
				'fecha_inicio',
				f'La fecha de inicio debe ser al menos {self.MIN_DIAS_ANTELACION} dias a partir de hoy '
				f'(fecha minima: {fecha_minima.strftime("%d/%m/%Y")}).'
			)

		if fecha_fin <= fecha_inicio:
			self.add_error('fecha_fin', 'La fecha de fin debe ser mayor a la fecha de inicio.')
			return cleaned_data

		dias_reserva = (fecha_fin - fecha_inicio).days
		if dias_reserva < self.MIN_DIAS_RESERVA:
			self.add_error(
				'fecha_fin',
				f'La reserva debe tener al menos {self.MIN_DIAS_RESERVA} dia(s) de duracion.'
			)

		if dias_reserva > self.MAX_DIAS_RESERVA:
			self.add_error(
				'fecha_fin',
				f'La reserva no puede superar los {self.MAX_DIAS_RESERVA} dias.'
			)

		return cleaned_data


class CheckoutPagoForm(forms.Form):
	"""Formulario del checkout de pago. Valida el método de pago y la franquicia.
	Los campos dinámicos de pago (número de tarjeta, CVV, etc.) se validan en la estrategia."""
	metodo_pago_nombre = forms.CharField(max_length=30)
	franquicia_id = forms.IntegerField(required=False)

	def clean_metodo_pago_nombre(self):
		"""
		Valida que el nombre del método de pago seleccionado sea válido y obtiene
		la estrategia de pago correspondiente para utilizarla durante el checkout.
		"""
		metodo_pago_nombre = self.cleaned_data['metodo_pago_nombre']

		try:
			estrategia = obtener_estrategia_pago(metodo_pago_nombre)
		except ValueError as exc:
			raise ValidationError('Debes seleccionar un metodo de pago valido.') from exc

		self.cleaned_data['metodo_pago_estrategia'] = estrategia
		return metodo_pago_nombre
