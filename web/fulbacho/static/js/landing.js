(() => {
  "use strict";

  const root = document.documentElement;
  const reduceMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  ).matches;

  root.classList.add("js");

  // Header compacto al hacer scroll.
  const header = document.querySelector(".site-header");

  const updateHeader = () => {
    if (!header) return;

    header.classList.toggle(
      "is-scrolled",
      window.scrollY > 18
    );
  };

  updateHeader();

  window.addEventListener(
    "scroll",
    updateHeader,
    { passive: true }
  );

  // Si el usuario prefiere menos movimiento,
  // mostramos todo sin animaciones.
  if (reduceMotion) {
    document
      .querySelectorAll("[data-reveal]")
      .forEach((el) => {
        el.classList.add("is-visible");
      });

    return;
  }

  // Animaciones de aparición al entrar en viewport.
  const revealItems = document.querySelectorAll(
    "[data-reveal]"
  );

  revealItems.forEach((el, index) => {
    const delay =
      el.dataset.revealDelay ??
      Math.min(index * 70, 280);

    el.style.setProperty(
      "--reveal-delay",
      `${delay}ms`
    );
  });

  const revealObserver = new IntersectionObserver(
    (entries, observer) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;

        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      });
    },
    {
      threshold: 0.14,
      rootMargin: "0px 0px -8% 0px",
    }
  );

  revealItems.forEach((el) => {
    revealObserver.observe(el);
  });

  // Parallax muy suave para la tarjeta visual del hero.
  const hero = document.querySelector(".hero");
  const heroVisual = document.querySelector(
    ".hero-visual"
  );

  if (
    hero &&
    heroVisual &&
    window.matchMedia("(pointer: fine)").matches
  ) {
    hero.addEventListener(
      "pointermove",
      (event) => {
        const rect = hero.getBoundingClientRect();

        const x =
          (event.clientX - rect.left) /
            rect.width -
          0.5;

        const y =
          (event.clientY - rect.top) /
            rect.height -
          0.5;

        heroVisual.style.setProperty(
          "--tilt-x",
          `${(-y * 3).toFixed(2)}deg`
        );

        heroVisual.style.setProperty(
          "--tilt-y",
          `${(x * 4).toFixed(2)}deg`
        );

        heroVisual.style.setProperty(
          "--shift-x",
          `${(x * 6).toFixed(2)}px`
        );

        heroVisual.style.setProperty(
          "--shift-y",
          `${(y * 6).toFixed(2)}px`
        );
      }
    );

    hero.addEventListener(
      "pointerleave",
      () => {
        heroVisual.style.setProperty(
          "--tilt-x",
          "0deg"
        );

        heroVisual.style.setProperty(
          "--tilt-y",
          "0deg"
        );

        heroVisual.style.setProperty(
          "--shift-x",
          "0px"
        );

        heroVisual.style.setProperty(
          "--shift-y",
          "0px"
        );
      }
    );
  }

  // Contadores opcionales.
  // Ejemplo:
  // <strong data-count="48">0</strong>
  const counters = document.querySelectorAll(
    "[data-count]"
  );

  const animateCounter = (el) => {
    const target = Number(el.dataset.count);

    if (!Number.isFinite(target)) return;

    const duration = 850;
    const start = performance.now();

    const frame = (now) => {
      const progress = Math.min(
        (now - start) / duration,
        1
      );

      const eased =
        1 - Math.pow(1 - progress, 3);

      el.textContent = Math.round(
        target * eased
      ).toLocaleString("es-AR");

      if (progress < 1) {
        requestAnimationFrame(frame);
      }
    };

    requestAnimationFrame(frame);
  };

  const counterObserver =
    new IntersectionObserver(
      (entries, observer) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;

          animateCounter(entry.target);
          observer.unobserve(entry.target);
        });
      },
      {
        threshold: 0.6,
      }
    );

  counters.forEach((el) => {
    counterObserver.observe(el);
  });
})();
