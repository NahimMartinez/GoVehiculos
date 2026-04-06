document.addEventListener("DOMContentLoaded", () => {
	const carousel = document.querySelector("[data-carousel='hero']");
	if (!carousel) {
		return;
	}

	const slides = Array.from(carousel.querySelectorAll("[data-slide]"));
	const dots = Array.from(carousel.querySelectorAll("[data-carousel-dot]"));
	const prevButton = carousel.querySelector("[data-carousel-prev]");
	const nextButton = carousel.querySelector("[data-carousel-next]");

	if (!slides.length) {
		return;
	}

	let activeIndex = 0;
	let timerId = null;

	const updateDots = (index) => {
		dots.forEach((dot, dotIndex) => {
			const isActive = dotIndex === index;
			dot.classList.toggle("bg-white", isActive);
			dot.classList.toggle("bg-white/30", !isActive);
			dot.setAttribute("aria-current", isActive ? "true" : "false");
		});
	};

	const showSlide = (index) => {
		slides.forEach((slide, slideIndex) => {
			slide.classList.toggle("hidden", slideIndex !== index);
		});
		activeIndex = index;
		updateDots(index);
	};

	const nextSlide = () => {
		const nextIndex = (activeIndex + 1) % slides.length;
		showSlide(nextIndex);
	};

	const prevSlide = () => {
		const prevIndex = (activeIndex - 1 + slides.length) % slides.length;
		showSlide(prevIndex);
	};

	const resetTimer = () => {
		if (timerId) {
			window.clearInterval(timerId);
		}
		timerId = window.setInterval(nextSlide, 10000);
	};

	dots.forEach((dot) => {
		dot.addEventListener("click", () => {
			const index = Number(dot.dataset.index);
			if (!Number.isNaN(index)) {
				showSlide(index);
				resetTimer();
			}
		});
	});

	if (prevButton) {
		prevButton.addEventListener("click", () => {
			prevSlide();
			resetTimer();
		});
	}

	if (nextButton) {
		nextButton.addEventListener("click", () => {
			nextSlide();
			resetTimer();
		});
	}

	showSlide(activeIndex);
	resetTimer();
});