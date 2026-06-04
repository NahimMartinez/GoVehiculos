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