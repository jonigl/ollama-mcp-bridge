/* Copy-to-clipboard for the hero's install command.
 *
 * Material ships a copy button, but only for fenced code blocks it has
 * highlighted; the hero's command is a bare <code> in a template, so it gets
 * its own. Wired through document$ because instant navigation swaps the body
 * without a page load, and a listener bound once on DOMContentLoaded would be
 * lost on the way back to the landing page.
 */
function initHeroCopy() {
  const button = document.querySelector(".omb-copy");
  if (!button) return;

  const target = document.querySelector(button.dataset.copyTarget);
  if (!target) return;

  button.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(target.textContent.trim());
      button.classList.add("omb-copy--done");
      button.setAttribute("aria-label", "Copied");
      setTimeout(() => {
        button.classList.remove("omb-copy--done");
        button.setAttribute("aria-label", "Copy to clipboard");
      }, 1600);
    } catch (error) {
      /* Clipboard access is denied outside a secure context — leave the text
         selectable rather than pretending the copy worked. */
      const range = document.createRange();
      range.selectNodeContents(target);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
    }
  });
}

if (typeof document$ !== "undefined") {
  document$.subscribe(initHeroCopy);
} else {
  document.addEventListener("DOMContentLoaded", initHeroCopy);
}
