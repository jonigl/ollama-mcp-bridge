/*
 * Drifts the hero's background layers at different rates as the page scrolls.
 *
 * Material ships instant navigation, so this cannot just run once on load:
 * `document$` emits on every page swap, and the previous page's listener has
 * to be torn down or they stack up.
 */

let teardown = null;

function initHeroParallax() {
  if (teardown) {
    teardown();
    teardown = null;
  }

  const hero = document.querySelector(".omb-hero");
  if (!hero) return;

  // Honour the OS setting: the layers stay where the CSS put them.
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (reduced.matches) return;

  const layers = Array.from(hero.querySelectorAll("[data-parallax]"));
  if (!layers.length) return;

  const rates = layers.map((el) => parseFloat(el.dataset.parallax) || 0);
  let ticking = false;
  let lastY = -1;

  const update = () => {
    ticking = false;
    const y = window.scrollY;
    if (y === lastY) return;
    lastY = y;

    // Once the hero has scrolled past, there is nothing left to move.
    if (y > hero.offsetHeight) return;

    layers.forEach((el, i) => {
      el.style.transform = `translate3d(0, ${(y * rates[i]).toFixed(2)}px, 0)`;
    });
  };

  const onScroll = () => {
    if (!ticking) {
      ticking = true;
      requestAnimationFrame(update);
    }
  };

  window.addEventListener("scroll", onScroll, { passive: true });
  update();

  teardown = () => {
    window.removeEventListener("scroll", onScroll);
    layers.forEach((el) => {
      el.style.transform = "";
    });
  };
}

if (typeof document$ !== "undefined") {
  document$.subscribe(initHeroParallax);
} else {
  document.addEventListener("DOMContentLoaded", initHeroParallax);
}
