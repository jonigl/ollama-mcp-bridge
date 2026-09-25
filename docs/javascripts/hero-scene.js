/*
 * Keeps the hero's scene moving without costing anything when it cannot be
 * seen.
 *
 * - Scroll parallax. Where the browser has scroll-driven animations the CSS
 *   does this on its own, off the main thread; this script only covers the
 *   browsers that do not, with the same arithmetic (see hero-scene.css).
 * - Pointer parallax, on devices with a mouse: the layers lean a few pixels
 *   away from the cursor, near ones more than far ones, eased so they settle
 *   rather than snap.
 * - Pausing the ambient loops (traffic, twinkling, water...) while the
 *   scene is off screen.
 *
 * Material ships instant navigation, so this cannot just run once on load:
 * `document$` emits on every page swap, and the previous page's listeners
 * and observers have to be torn down or they stack up.
 */

const SCROLL_TIMELINES =
  window.CSS &&
  CSS.supports("animation-timeline: view()") &&
  CSS.supports("timeline-scope: --a");

let teardown = null;

function initHeroScene() {
  if (teardown) {
    teardown();
    teardown = null;
  }

  const hero = document.querySelector(".omb-hero");
  if (!hero) return;

  const cleanups = [];
  const layers = [];
  const on = (target, type, fn, opts) => {
    target.addEventListener(type, fn, opts);
    cleanups.push(() => target.removeEventListener(type, fn, opts));
  };

  // Filled in below only when there is parallax to drive.
  let render = null;
  let frame = 0;
  const schedule = () => {
    if (render && !frame) frame = requestAnimationFrame(render);
  };
  cleanups.push(() => cancelAnimationFrame(frame));

  // Two things to watch. The loops pause whenever the scene itself is out of
  // view — on a phone the hero is several screens of text above it, and
  // there is no point ticking traffic nobody can see. The parallax only stops
  // once the whole hero is gone, because the glows behind the text still move.
  const stage = hero.querySelector(".omb-scene__stage");
  let visible = true;
  const io = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.target === stage) {
          hero.classList.toggle("omb-hero--idle", !entry.isIntersecting);
        } else {
          visible = entry.isIntersecting;
          if (visible) schedule();
        }
      }
    },
    { rootMargin: "120px 0px" },
  );
  io.observe(hero);
  if (stage) io.observe(stage);
  cleanups.push(() => io.disconnect());

  teardown = () => {
    cleanups.forEach((fn) => fn());
    layers.forEach(({ el }) => {
      el.style.transform = "";
      el.style.translate = "";
    });
    hero.classList.remove("omb-hero--idle");
  };

  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  hero.querySelectorAll(".omb-par").forEach((el) => {
    layers.push({
      el,
      rate: parseFloat(el.style.getPropertyValue("--r")) || 0,
      top: el.dataset.anchor === "top",
    });
  });

  const byScroll = !SCROLL_TIMELINES;
  const byPointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  if (!byScroll && !byPointer) return;

  // Where the stage comes to rest: the scroll offset at which the hero's
  // bottom edge meets the bottom of the viewport.
  let rest = 0;
  let sceneH = 0;
  let vh = window.innerHeight;
  const measure = () => {
    vh = window.innerHeight;
    rest = hero.getBoundingClientRect().bottom + window.scrollY - vh;
    sceneH = stage ? stage.offsetHeight : 0;
  };

  let aim = 0; // pointer target, -1 (left edge) to 1 (right edge)
  let lean = 0; // where the layers currently are on the way to it

  render = () => {
    frame = 0;
    if (!visible) return;

    const y = window.scrollY;
    const s = Math.min(Math.max(y - rest, -sceneH), vh);
    lean += (aim - lean) * 0.08;

    for (const { el, rate, top } of layers) {
      if (byScroll) {
        const d = (top ? Math.min(y, vh) : s) * rate;
        el.style.transform = `translate3d(0, ${d.toFixed(1)}px, 0)`;
      }
      if (byPointer) {
        // Nearness is what the layer does not resist: the shore leans most.
        el.style.translate = `${(-lean * (1 - rate) * 14).toFixed(2)}px 0`;
      }
    }

    if (byPointer && Math.abs(aim - lean) > 0.002) schedule();
  };

  measure();
  const ro = new ResizeObserver(() => {
    measure();
    schedule();
  });
  ro.observe(hero);
  cleanups.push(() => ro.disconnect());
  on(window, "resize", measure, { passive: true });

  if (byScroll) on(window, "scroll", schedule, { passive: true });
  if (byPointer) {
    on(
      window,
      "pointermove",
      (e) => {
        aim = (e.clientX / window.innerWidth) * 2 - 1;
        schedule();
      },
      { passive: true },
    );
  }

  schedule();
}

if (typeof document$ !== "undefined") {
  document$.subscribe(initHeroScene);
} else {
  document.addEventListener("DOMContentLoaded", initHeroScene);
}
