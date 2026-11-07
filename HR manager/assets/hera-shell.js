(() => {
  const body = document.body;
  const sidebar = document.getElementById("hera-shell-sidebar");
  const backdrop = document.querySelector("[data-hera-shell-close]");
  if (!body || !sidebar || !backdrop || body.dataset.heraShellReady === "true") return;

  body.dataset.heraShellReady = "true";
  body.classList.add("hera-unified-app");

  const content = document.createElement("div");
  content.className = "hera-shell-content";
  const homeTarget = sidebar.querySelector(".hera-shell-brand")?.getAttribute("href") || "/BIC2_Mvp/employee.php";
  const mobileBar = document.createElement("div");
  mobileBar.className = "hera-shell-mobilebar";
  mobileBar.innerHTML = `
    <a class="hera-shell-mobile-brand" href="${homeTarget}">
      <img src="/BIC2_Mvp/assets/animated-logo.gif" alt="" width="40" height="40" />
      <span>HERA <small>الموارد البشرية</small></span>
    </a>
    <button class="hera-shell-menu-toggle" type="button" aria-controls="hera-shell-sidebar" aria-expanded="false">
      <svg viewBox="0 0 24 24" width="21" height="21" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16" stroke-linecap="round" /></svg>
      <span>القائمة</span>
    </button>`;

  const preserved = new Set([sidebar, backdrop]);
  for (const node of [...body.childNodes]) {
    if (preserved.has(node) || (node.nodeType === Node.ELEMENT_NODE && ["SCRIPT", "STYLE", "LINK"].includes(node.tagName))) continue;
    content.append(node);
  }

  content.prepend(mobileBar);
  sidebar.after(content);

  const legacySidebars = content.querySelectorAll("aside.sidebar, aside.hera-extra-sidebar");
  legacySidebars.forEach((item) => item.setAttribute("aria-hidden", "true"));
  content.querySelectorAll("header > div").forEach((item) => {
    if (item.className?.includes("overflow-x-auto") && item.className?.includes("border-t")) item.hidden = true;
  });

  const toggle = mobileBar.querySelector(".hera-shell-menu-toggle");
  const navControls = sidebar.querySelectorAll("a, button[data-hera-section]");
  let previousFocus = null;

  function closeMenu({ restoreFocus = false } = {}) {
    sidebar.classList.remove("is-open");
    backdrop.hidden = true;
    toggle.setAttribute("aria-expanded", "false");
    body.classList.remove("hera-menu-open");
    if (restoreFocus) previousFocus?.focus();
  }

  function openMenu() {
    previousFocus = document.activeElement;
    backdrop.hidden = false;
    sidebar.classList.add("is-open");
    toggle.setAttribute("aria-expanded", "true");
    body.classList.add("hera-menu-open");
    requestAnimationFrame(() => sidebar.querySelector("a")?.focus());
  }

  toggle.addEventListener("click", () => {
    sidebar.classList.contains("is-open") ? closeMenu({ restoreFocus: true }) : openMenu();
  });
  backdrop.addEventListener("click", () => closeMenu({ restoreFocus: true }));
  navControls.forEach((control) => control.addEventListener("click", () => closeMenu()));
  const sectionLinks = sidebar.querySelectorAll("[data-hera-section]");
  function markSection(name) {
    sectionLinks.forEach((link) => {
      const active = link.dataset.heraSection === name;
      link.classList.toggle("is-active", active);
      if (active) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
  }
  if (typeof window.showSection === "function" && sectionLinks.length) {
    const originalShowSection = window.showSection;
    window.showSection = (name) => {
      originalShowSection(name);
      markSection(name);
    };
    sectionLinks.forEach((link) => link.addEventListener("click", () => window.showSection(link.dataset.heraSection)));
    const requestedSection = new URLSearchParams(window.location.search).get("section");
    if (requestedSection && [...sectionLinks].some((link) => link.dataset.heraSection === requestedSection)) {
      window.showSection(requestedSection);
    }
  }
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && sidebar.classList.contains("is-open")) {
      closeMenu({ restoreFocus: true });
    }
  });
  window.addEventListener("resize", () => {
    if (window.matchMedia("(min-width: 901px)").matches) closeMenu();
  });

  if (!body.querySelector("#themeToggleBtn")) {
    const savedTheme = localStorage.getItem("theme");
    body.classList.toggle("light-mode", savedTheme === "light");
  }

  content.querySelectorAll("table").forEach((table) => {
    if (table.parentElement?.classList.contains("hera-table-scroll")) return;
    const wrapper = document.createElement("div");
    wrapper.className = "hera-table-scroll";
    table.before(wrapper);
    wrapper.append(table);
  });
})();
