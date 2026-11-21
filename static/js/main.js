/* 交互增强：移动端导航、论文筛选/搜索、年份分组显示 */
(function () {
  "use strict";

  var toggle = document.querySelector(".nav-toggle");
  var nav = document.getElementById("nav-list");
  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
    nav.addEventListener("click", function (e) {
      if (e.target.tagName === "A") {
        nav.classList.remove("open");
        toggle.setAttribute("aria-expanded", "false");
      }
    });
  }

  // 导航滚动阴影 + 回到顶部按钮（所有页面生效，置于论文筛选的提前 return 之前）
  var header = document.querySelector(".site-header");
  var toTop = document.createElement("button");
  toTop.className = "to-top";
  toTop.type = "button";
  toTop.setAttribute("aria-label", "回到顶部");
  toTop.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 19V5M5 12l7-7 7 7"/></svg>';
  document.body.appendChild(toTop);
  function onScroll() {
    var y = window.scrollY || window.pageYOffset || 0;
    if (header) header.classList.toggle("is-scrolled", y > 8);
    toTop.classList.toggle("show", y > 480);
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onScroll);
  onScroll();
  toTop.addEventListener("click", function () {
    var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" });
  });

  var input = document.getElementById("pub-search");
  var yearSel = document.getElementById("pub-year");
  var typeSel = document.getElementById("pub-type");
  var list = document.getElementById("pub-list");
  var counter = document.getElementById("pub-count");
  if (!list) return;

  var items = Array.prototype.slice.call(list.querySelectorAll(".pub-item"));
  var headings = Array.prototype.slice.call(list.querySelectorAll(".year-heading"));
  var empty = document.getElementById("pub-empty");

  function apply() {
    var q = (input && input.value || "").trim().toLowerCase();
    var y = yearSel && yearSel.value || "all";
    var t = typeSel && typeSel.value || "all";
    var shown = 0;

    items.forEach(function (it) {
      var ok = true;
      if (q && (it.dataset.search || "").indexOf(q) === -1) ok = false;
      if (ok && y !== "all" && it.dataset.year !== y) ok = false;
      if (ok && t !== "all" && it.dataset.type !== t) ok = false;
      it.style.display = ok ? "" : "none";
      if (ok) shown++;
    });

    headings.forEach(function (h) {
      var yv = h.dataset.year;
      var anyVisible = items.some(function (it) {
        return it.dataset.year === yv && it.style.display !== "none";
      });
      h.style.display = anyVisible ? "" : "none";
    });

    if (counter) counter.textContent = shown + " / " + items.length + " 条";
    if (empty) empty.style.display = shown === 0 ? "block" : "none";
  }

  [input, yearSel, typeSel].forEach(function (el) {
    if (!el) return;
    el.addEventListener(el === input ? "input" : "change", apply);
  });

  var clear = document.getElementById("pub-clear");
  if (clear) {
    clear.addEventListener("click", function () {
      if (input) input.value = "";
      if (yearSel) yearSel.value = "all";
      if (typeSel) typeSel.value = "all";
      apply();
    });
  }
  apply();
})();
