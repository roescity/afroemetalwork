/* Minimal dependency-free lightbox.
   Any <a data-lightbox="group"> opens its href in a full-screen
   overlay; links sharing a group value are browsable with
   arrows / arrow keys. Esc or backdrop click closes. */

(function () {
  "use strict";

  var links = Array.prototype.slice.call(
    document.querySelectorAll("a[data-lightbox]")
  );
  if (!links.length) return;

  var current = -1;
  var overlay = null;

  function build() {
    overlay = document.createElement("div");
    overlay.className = "lb-overlay";
    overlay.innerHTML =
      '<button class="lb-close" aria-label="Close">×</button>' +
      '<button class="lb-prev" aria-label="Previous">‹</button>' +
      '<button class="lb-next" aria-label="Next">›</button>' +
      '<img alt="">' +
      '<p class="lb-count"></p>';
    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) close();
    });
    overlay.querySelector(".lb-close").addEventListener("click", close);
    overlay.querySelector(".lb-prev").addEventListener("click", function () { step(-1); });
    overlay.querySelector(".lb-next").addEventListener("click", function () { step(1); });
    document.body.appendChild(overlay);
  }

  function group(i) {
    var g = links[i].getAttribute("data-lightbox");
    return links.filter(function (l) { return l.getAttribute("data-lightbox") === g; });
  }

  function show(i) {
    current = i;
    if (!overlay) build();
    var img = overlay.querySelector("img");
    img.src = links[i].href;
    var inner = links[i].querySelector("img");
    img.alt = inner ? inner.alt : "";
    var g = group(i);
    var many = g.length > 1;
    overlay.querySelector(".lb-prev").style.display = many ? "" : "none";
    overlay.querySelector(".lb-next").style.display = many ? "" : "none";
    overlay.querySelector(".lb-count").textContent =
      many ? (g.indexOf(links[i]) + 1) + " / " + g.length : "";
    overlay.style.display = "flex";
    document.body.style.overflow = "hidden";
  }

  function step(dir) {
    var g = group(current);
    var pos = g.indexOf(links[current]);
    var next = g[(pos + dir + g.length) % g.length];
    show(links.indexOf(next));
  }

  function close() {
    if (overlay) overlay.style.display = "none";
    document.body.style.overflow = "";
    current = -1;
  }

  links.forEach(function (link, i) {
    link.addEventListener("click", function (e) {
      e.preventDefault();
      show(i);
    });
  });

  document.addEventListener("keydown", function (e) {
    if (current < 0) return;
    if (e.key === "Escape") close();
    else if (e.key === "ArrowLeft") step(-1);
    else if (e.key === "ArrowRight") step(1);
  });
})();
