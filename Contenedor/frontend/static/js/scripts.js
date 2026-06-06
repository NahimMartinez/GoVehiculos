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
	const cancelReservaModal = document.querySelector('[data-cancel-reserva-modal]');
	const cancelReservaTitle = cancelReservaModal?.querySelector('[data-cancel-reserva-title]');
	const cancelReservaDetails = cancelReservaModal?.querySelector('[data-cancel-reserva-details]');
	const cancelReservaConfirm = cancelReservaModal?.querySelector('[data-cancel-reserva-confirm]');
	const cancelReservaCloseButtons = cancelReservaModal
		? Array.from(cancelReservaModal.querySelectorAll('[data-cancel-reserva-close]'))
		: [];
	let activeCancelReservaForm = null;

	const closeCancelReservaModal = () => {
		if (!cancelReservaModal) {
			return;
		}

		cancelReservaModal.classList.add('hidden');
		cancelReservaModal.setAttribute('aria-hidden', 'true');
		activeCancelReservaForm = null;
	};

	const openCancelReservaModal = (form) => {
		if (!cancelReservaModal || !cancelReservaTitle || !cancelReservaDetails || !cancelReservaConfirm) {
			return;
		}

		activeCancelReservaForm = form;
		cancelReservaTitle.textContent = form.getAttribute('data-reserva-titulo') || 'esta reserva';
		cancelReservaDetails.textContent = form.getAttribute('data-reserva-detalle') || 'Revisá los datos antes de continuar.';
		cancelReservaModal.classList.remove('hidden');
		cancelReservaModal.setAttribute('aria-hidden', 'false');
		cancelReservaConfirm.focus();
	};

	if (cancelReservaModal) {
		cancelReservaCloseButtons.forEach((button) => {
			button.addEventListener('click', closeCancelReservaModal);
		});

		cancelReservaModal.addEventListener('click', (event) => {
			if (event.target === cancelReservaModal) {
				closeCancelReservaModal();
			}
		});

		document.addEventListener('keydown', (event) => {
			if (event.key === 'Escape' && !cancelReservaModal.classList.contains('hidden')) {
				closeCancelReservaModal();
			}
		});

		cancelReservaConfirm?.addEventListener('click', () => {
			if (activeCancelReservaForm) {
				activeCancelReservaForm.submit();
			}
		});
	}

	// Resumen dinámico del formulario de reserva (sin método de pago — eso se elige en el checkout)
	const reservaForm = document.querySelector('[data-reserva-form]');
	if (reservaForm) {
		const vehicleSelect = reservaForm.querySelector('[data-vehicle-select]');
		const selectedVehicleCard = reservaForm.querySelector('[data-selected-vehicle-card]');
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
			if (!resumenDias || !resumenTotal || !resumenAyuda) {
				return;
			}

			const { name: vehicleName, price: pricePerDay } = getSelectedVehicleInfo();
			const days = calculateDays();
			const total = days > 0 && pricePerDay > 0 ? days * pricePerDay : 0;

			resumenDias.textContent = String(days);
			resumenTotal.textContent = new Intl.NumberFormat('es-AR', {
				style: 'currency',
				currency: 'ARS',
				maximumFractionDigits: 2,
			}).format(total);

			if (vehicleName && days > 0) {
				resumenAyuda.textContent = 'El recargo o descuento se aplicará según el método de pago que elijas en el checkout.';
				return;
			}

			resumenAyuda.textContent = 'Elegí un vehículo y las fechas para ver el cálculo. El método de pago se selecciona en el siguiente paso.';
		};

		[vehicleSelect, ...fechaReservaInputs].forEach((element) => {
			if (element) {
				element.addEventListener('change', updateSummary);
				element.addEventListener('input', updateSummary);
			}
		});

		updateSummary();
	}

	document.querySelectorAll('[data-cancel-reserva-form]').forEach((form) => {
		form.addEventListener('submit', (event) => {
			event.preventDefault();
			openCancelReservaModal(form);
		});
	});
});