// Scripts globales
document.addEventListener('click', (event) => {
	const dismissButton = event.target.closest('[data-dismiss-message]');

	if (!dismissButton) {
		return;
	}

	const messageBanner = dismissButton.closest('[data-message-banner]');
	if (messageBanner) {
		messageBanner.remove();
	}
});

document.addEventListener('DOMContentLoaded', () => {
	const reservaForm = document.querySelector('[data-reserva-form]');
	if (!reservaForm) {
		return;
	}

	const metodoSelect = reservaForm.querySelector('[data-metodo-select]');
	const vehicleSelect = reservaForm.querySelector('[data-vehicle-select]');
	const selectedVehicleCard = reservaForm.querySelector('[data-selected-vehicle-card]');
	const resumenMetodo = reservaForm.querySelector('[data-resumen-metodo]');
	const resumenDias = reservaForm.querySelector('[data-resumen-dias]');
	const resumenTotal = reservaForm.querySelector('[data-resumen-total]');
	const resumenAyuda = reservaForm.querySelector('[data-resumen-ayuda]');
	const fechaInicioInput = reservaForm.querySelector('#fecha_inicio');
	const fechaFinInput = reservaForm.querySelector('#fecha_fin');
	const fechaReservaInputs = [fechaInicioInput, fechaFinInput].filter(Boolean);

	const parseNumber = (value) => {
		const parsed = Number.parseFloat(value);
		return Number.isFinite(parsed) ? parsed : 0;
	};

	const normalizeText = (value) => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();

	const paymentStrategies = {
		'tarjeta_credito': { factor: 1.1, help: 'Tarjeta de crédito aplica un recargo del 10%.' },
		'tarjeta_debito': { factor: 1.0, help: 'Tarjeta de débito mantiene el precio base.' },
		'transferencia': { factor: 0.95, help: 'Transferencia aplica un descuento del 5%.' },
	};

	const getSelectedVehicleInfo = () => {
		if (selectedVehicleCard) {
			return {
				name: selectedVehicleCard.getAttribute('data-vehicle-name') || 'Vehículo seleccionado',
				price: parseNumber(selectedVehicleCard.getAttribute('data-vehicle-price')),
			};
		}

		if (!vehicleSelect) {
			return { name: '', price: 0 };
		}

		const selectedOption = vehicleSelect.options[vehicleSelect.selectedIndex];
		if (!selectedOption || !selectedOption.value) {
			return { name: '', price: 0 };
		}

		return {
			name: selectedOption.getAttribute('data-vehiculo-nombre') || selectedOption.textContent.trim(),
			price: parseNumber(selectedOption.getAttribute('data-precio')),
		};
	};

	const calculateDays = () => {
		if (!fechaInicioInput || !fechaFinInput || !fechaInicioInput.value || !fechaFinInput.value) {
			return 0;
		}

		const startDate = new Date(`${fechaInicioInput.value}T00:00:00`);
		const endDate = new Date(`${fechaFinInput.value}T00:00:00`);
		const diffMs = endDate.getTime() - startDate.getTime();

		if (!Number.isFinite(diffMs) || diffMs <= 0) {
			return 0;
		}

		return Math.round(diffMs / 86400000);
	};

	const updateSummary = () => {
		if (!resumenMetodo || !resumenDias || !resumenTotal || !resumenAyuda) {
			return;
		}

		const { name: vehicleName, price: pricePerDay } = getSelectedVehicleInfo();
		const selectedMethod = metodoSelect && metodoSelect.value ? metodoSelect.options[metodoSelect.selectedIndex] : null;
		const methodName = selectedMethod && selectedMethod.value ? selectedMethod.textContent.trim() : 'Seleccionar';
		const normalizedMethod = selectedMethod && selectedMethod.value
			? selectedMethod.getAttribute('data-metodo-clave') || normalizeText(selectedMethod.value)
			: '';
		const strategy = paymentStrategies[normalizedMethod] || { factor: 1, help: 'Elegí un método de pago para ver el cálculo.' };
		const days = calculateDays();
		const baseTotal = days > 0 && pricePerDay > 0 ? days * pricePerDay : 0;
		const total = baseTotal > 0 ? baseTotal * strategy.factor : 0;

		resumenMetodo.textContent = methodName;
		resumenDias.textContent = String(days);
		resumenTotal.textContent = new Intl.NumberFormat('es-AR', {
			style: 'currency',
			currency: 'ARS',
			maximumFractionDigits: 2,
		}).format(total);

		if (methodName !== 'Seleccionar' && vehicleName && days > 0) {
			resumenAyuda.textContent = strategy.help;
			return;
		}

		if (methodName === 'Seleccionar') {
			resumenAyuda.textContent = 'Elegí un método de pago para completar la reserva.';
			return;
		}

		resumenAyuda.textContent = 'Elegí un vehículo, las fechas y un método de pago para ver el cálculo.';
	};

	[metodoSelect, vehicleSelect, ...fechaReservaInputs].forEach((element) => {
		if (element) {
			element.addEventListener('change', updateSummary);
			element.addEventListener('input', updateSummary);
		}
	});

	updateSummary();
});