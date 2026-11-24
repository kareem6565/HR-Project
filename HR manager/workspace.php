<?php
require_once __DIR__ . '/includes/auth.php';

requireLogin();
if (($_SESSION['role'] ?? '') !== 'hr') {
    redirect(roleHome($_SESSION['role'] ?? 'employee'));
}
$name = htmlspecialchars((string)($_SESSION['name'] ?? ''), ENT_QUOTES, 'UTF-8');
?>
<!doctype html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="theme-color" content="#f8f7f2" />
  <title>اختيار مساحة العمل — HERA</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800;900&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="/BIC2_Mvp/assets/hera-brand.css?v=hera-motion-20261116-1" />
  <script src="/BIC2_Mvp/assets/hera-language.js" defer></script>
  <style>
    :root {
      color-scheme: light;
      --workspace-ink: #1b3a3a;
      --workspace-body: #536764;
      --workspace-muted: #71817d;
      --workspace-line: #dce5e1;
      --workspace-paper: #f8f7f2;
      --workspace-white: #fff;
      --workspace-gold: #e9d98a;
      --workspace-blue: #6fa8b8;
      --workspace-ease: cubic-bezier(.2,.7,.25,1);
    }

    * { box-sizing: border-box; }
    html { min-width: 320px; background: var(--workspace-paper); }
    body.hera-theme.workspace-page {
      min-height: 100vh;
      margin: 0;
      color: var(--workspace-ink) !important;
      background: var(--workspace-paper) !important;
      font-family: Cairo, Inter, system-ui, sans-serif;
    }
    .workspace-shell {
      width: min(1160px, calc(100% - 64px));
      margin-inline: auto;
      padding-block: 28px 64px;
    }
    .workspace-top {
      min-height: 68px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 24px;
      padding: 0 2px 18px;
      color: var(--workspace-ink) !important;
      background: transparent !important;
      border: 0 !important;
      border-bottom: 1px solid rgba(27,58,58,.12) !important;
      border-radius: 0 !important;
      box-shadow: none !important;
      backdrop-filter: none !important;
    }
    body.hera-theme.workspace-page header.workspace-top {
      color: var(--workspace-ink) !important;
      background: transparent !important;
      border: 0 !important;
      border-bottom: 1px solid rgba(27,58,58,.12) !important;
      border-radius: 0 !important;
      box-shadow: none !important;
      backdrop-filter: none !important;
    }
    .workspace-brand { display: inline-flex; align-items: center; gap: 11px; color: var(--workspace-ink); text-decoration: none; }
    .workspace-brand-mark { display: block; width: 43px; height: 43px; border-radius: 13px; box-shadow: 0 3px 9px rgba(8,42,36,.12); }
    .workspace-brand-copy { display: grid; gap: 2px; text-align: start; }
    .workspace-brand-copy strong { color: var(--workspace-ink); font: 800 17px/1 Inter, Cairo, sans-serif; letter-spacing: .045em; }
    .workspace-brand-copy small { color: var(--workspace-muted); font: 500 10px/1.35 Inter, Cairo, sans-serif; }
    .top-actions { display: flex; align-items: center; gap: 9px; }
    .logout-link {
      min-height: 40px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 0 13px;
      border: 1px solid #d8e2dd;
      border-radius: 10px;
      color: #31534b !important;
      background: rgba(255,255,255,.62) !important;
      font-size: 13px;
      font-weight: 700;
      text-decoration: none;
      transition: background-color 160ms ease, border-color 160ms ease, transform 160ms var(--workspace-ease);
    }
    .logout-link svg { width: 16px; height: 16px; color: #648078; }
    .logout-link:hover { border-color: #b8cbc5; background: #fff !important; transform: translateY(-1px); }
    .workspace-top .hera-language-toggle { min-height: 40px; margin: 0; padding: 0 11px; border: 1px solid #d8e2dd; border-radius: 10px; color: #31534b; background: rgba(255,255,255,.62); box-shadow: none; font-size: 12px; font-weight: 700; }
    .workspace-top .hera-language-toggle:hover { border-color: #b8cbc5; background: #fff; }
    .workspace-top :focus-visible,
    .workspace-option:focus-visible { outline: 3px solid #2e8492; outline-offset: 4px; }

      .workspace-main { padding-top: clamp(34px, 6vw, 72px); }
    .workspace-hero { animation: workspace-hero-enter 360ms var(--workspace-ease); }
    .workspace-option { animation: workspace-option-enter 360ms var(--workspace-ease); }
    .workspace-option:nth-child(2) { animation-delay: 65ms; }
    @keyframes workspace-hero-enter { from { opacity: 0; transform: translateY(9px); } to { opacity: 1; transform: none; } }
    @keyframes workspace-option-enter { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
    .workspace-hero {
      position: relative;
      isolation: isolate;
      min-height: 280px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(220px, .52fr);
      align-items: center;
      gap: 28px;
      overflow: hidden;
      padding: clamp(30px, 5.5vw, 66px);
      border-radius: 28px;
      color: #fff;
      background: var(--workspace-ink);
      box-shadow: 0 20px 50px rgba(27,58,58,.12);
    }
    .workspace-hero::before,
    .workspace-hero::after { content: ""; position: absolute; z-index: -1; pointer-events: none; }
    .workspace-hero::before {
      width: 360px; aspect-ratio: 1; inset-inline-end: -80px; top: -208px;
      border: 1px solid rgba(233,217,138,.34); border-radius: 50%;
      box-shadow: 0 0 0 34px rgba(233,217,138,.04), 0 0 0 82px rgba(111,168,184,.07);
    }
    .workspace-hero::after {
      width: 250px; height: 250px; inset-inline-start: -130px; bottom: -180px;
      border: 1px solid rgba(111,168,184,.45); border-radius: 50%;
      box-shadow: 0 0 0 26px rgba(111,168,184,.05);
    }
    .hero-copy { max-width: 660px; }
    .hero-kicker {
      display: inline-flex;
      align-items: center;
      gap: 9px;
      margin: 0 0 15px;
      color: #f0dfa0;
      font-size: 13px;
      font-weight: 800;
      letter-spacing: .035em;
    }
    .hero-kicker::before { content: ""; width: 22px; height: 2px; border-radius: 2px; background: var(--workspace-gold); }
    .hero-title {
      max-width: 700px;
      margin: 0;
      color: #fff !important;
      font-size: clamp(30px, 4.4vw, 50px);
      font-weight: 800;
      line-height: 1.42;
      letter-spacing: -.035em;
      text-wrap: balance;
    }
    .hero-description { max-width: 610px; margin: 12px 0 0; color: rgba(245,249,247,.78); font-size: clamp(15px,1.5vw,17px); line-height: 1.9; }
    .hero-mark {
      width: min(100%, 214px);
      aspect-ratio: 1;
      justify-self: center;
      display: grid;
      place-items: center;
      border: 1px solid rgba(233,217,138,.55);
      border-radius: 50%;
      color: var(--workspace-gold);
      background: rgba(255,255,255,.035);
      box-shadow: 0 0 0 15px rgba(255,255,255,.025), inset 0 0 0 13px rgba(255,255,255,.025);
    }
    .hero-mark svg { width: 88px; height: 88px; }

    .workspace-section { padding-top: clamp(34px, 5vw, 58px); }
    .section-heading { display: flex; align-items: end; justify-content: space-between; gap: 20px; margin-bottom: 18px; }
    .section-heading h2 { margin: 0; color: var(--workspace-ink); font-size: clamp(21px,2.5vw,27px); font-weight: 800; line-height: 1.4; }
    .section-heading p { max-width: 400px; margin: 0; color: var(--workspace-muted); font-size: 14px; line-height: 1.7; }
    .workspace-options { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 18px; }
    .workspace-option {
      position: relative;
      min-height: 256px;
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      padding: clamp(23px,3vw,32px);
      overflow: hidden;
      border: 1px solid var(--workspace-line);
      border-radius: 20px;
      color: var(--workspace-ink) !important;
      background: var(--workspace-white);
      text-decoration: none;
      box-shadow: 0 8px 24px rgba(27,58,58,.045);
      transition: transform 180ms var(--workspace-ease), border-color 180ms ease, box-shadow 180ms ease;
    }
    .workspace-option::before { content: ""; position: absolute; inset-block: 0; inset-inline-start: 0; width: 4px; background: var(--workspace-blue); transform: scaleY(.22); transform-origin: center; transition: transform 180ms var(--workspace-ease); }
    .workspace-option--recruitment::before { background: var(--workspace-gold); }
    .workspace-option:hover { transform: translateY(-3px); border-color: #b7cbc5; box-shadow: 0 16px 34px rgba(27,58,58,.10); }
    .workspace-option:hover::before { transform: scaleY(1); }
    .option-top { width: 100%; display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 20px; }
    .option-symbol { width: 52px; height: 52px; flex: 0 0 auto; display: grid; place-items: center; border-radius: 15px; color: var(--workspace-ink); background: #f3edcf; }
    .workspace-option--hr .option-symbol { background: #e5f0f1; color: #285d65; }
    .option-symbol svg { width: 25px; height: 25px; }
    .option-index { padding-top: 7px; color: #8a9995; font-size: 12px; font-weight: 700; }
    .workspace-option h3 { margin: 0 0 8px; color: var(--workspace-ink); font-size: 21px; font-weight: 800; line-height: 1.45; }
    .workspace-option p { max-width: 470px; margin: 0; color: var(--workspace-body); font-size: 14px; line-height: 1.9; }
    .option-action { width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 14px; margin-top: auto; padding-top: 24px; color: var(--workspace-ink); font-size: 14px; font-weight: 800; }
    .action-icon { width: 34px; height: 34px; flex: 0 0 auto; display: grid; place-items: center; border: 1px solid var(--workspace-line); border-radius: 50%; transition: background-color 180ms ease, color 180ms ease, transform 180ms var(--workspace-ease); }
    .action-icon svg { width: 16px; height: 16px; }
    .workspace-option:hover .action-icon { color: #fff; background: var(--workspace-ink); transform: translateX(-2px); }
    html[dir="ltr"] .workspace-option:hover .action-icon { transform: translateX(2px); }

    .workspace-transition {
      position: fixed;
      z-index: 9999;
      inset: 0;
      display: grid;
      place-items: center;
      overflow: hidden;
      visibility: hidden;
      pointer-events: none;
      background: var(--workspace-ink);
    }
    .workspace-transition::before,
    .workspace-transition::after { content: ""; position: absolute; pointer-events: none; }
    .workspace-transition::before { inset: 0; background: var(--workspace-ink); }
    .workspace-transition::after { width: 170px; height: 170px; border: 1px solid rgba(233,217,138,.6); border-radius: 50%; box-shadow: 0 0 0 18px rgba(233,217,138,.08), 0 0 0 48px rgba(111,168,184,.07); }
    .workspace-transition-mark { position: relative; z-index: 1; width: 66px; height: 66px; display: grid; place-items: center; border: 1px solid rgba(255,255,255,.26); border-radius: 20px; color: var(--workspace-gold); background: rgba(255,255,255,.08); font-size: 14px; font-weight: 900; letter-spacing: .1em; opacity: 0; }
    body[data-workspace-exit] .workspace-transition { visibility: visible; }
    body[data-workspace-exit="recruitment"] .workspace-transition::before { animation: recruitment-wipe 440ms var(--workspace-ease) both; background: #173a39; }
    body[data-workspace-exit="recruitment"] .workspace-transition::after { animation: recruitment-orbit 440ms ease-out both; }
    body[data-workspace-exit="recruitment"] .workspace-transition-mark { animation: workflow-mark-in 260ms 100ms ease-out both; }
    body[data-workspace-exit="hr"] .workspace-transition::before { animation: hr-reveal 520ms cubic-bezier(.16,.72,.2,1) both; background: #204c57; }
    body[data-workspace-exit="hr"] .workspace-transition::after { border-color: rgba(111,168,184,.72); box-shadow: 0 0 0 18px rgba(111,168,184,.1), 0 0 0 48px rgba(255,255,255,.04); animation: hr-ripple 520ms ease-out both; }
    body[data-workspace-exit="hr"] .workspace-transition-mark { color: #b5dce3; animation: workflow-mark-in 300ms 140ms ease-out both; }
    @keyframes recruitment-wipe { from { transform: translateY(102%); } to { transform: translateY(0); } }
    @keyframes recruitment-orbit { from { transform: scale(.35) rotate(-35deg); opacity: 0; } to { transform: scale(1) rotate(0); opacity: 1; } }
    @keyframes hr-reveal { from { clip-path: circle(0 at 50% 55%); } to { clip-path: circle(150% at 50% 55%); } }
    @keyframes hr-ripple { from { transform: scale(.3); opacity: 0; } to { transform: scale(1.2); opacity: .75; } }
    @keyframes workflow-mark-in { from { transform: translateY(8px) scale(.92); opacity: 0; } to { transform: none; opacity: 1; } }

    @media (max-width: 760px) {
      .workspace-shell { width: min(100% - 40px, 600px); padding-block: 20px 42px; }
      .workspace-hero { min-height: 0; grid-template-columns: minmax(0,1fr) 112px; gap: 16px; padding: 30px 26px; border-radius: 22px; }
      .hero-mark { width: 104px; }
      .hero-mark svg { width: 52px; height: 52px; }
      .hero-title { font-size: clamp(27px,5vw,36px); }
      .workspace-option { min-height: 248px; }
      .section-heading { align-items: flex-start; flex-direction: column; gap: 5px; }
    }
    @media (max-width: 540px) {
      .workspace-shell { width: calc(100% - 32px); padding-block: 16px 32px; }
      .workspace-top { min-height: 58px; gap: 10px; padding-bottom: 14px; }
      .workspace-brand-mark { width: 39px; height: 39px; border-radius: 11px; }
      .top-actions { gap: 6px; }
      .workspace-brand-copy small { font-size: 9px; }
      .logout-link { min-height: 38px; padding-inline: 10px; border-radius: 10px; font-size: 12px; white-space: nowrap; }
      .workspace-top .hera-language-toggle { min-height: 38px; padding-inline: 9px; font-size: 12px; }
      .workspace-main { padding-top: 22px; }
      .workspace-hero { grid-template-columns: minmax(0,1fr); padding: 25px 21px; }
      .hero-mark { display: none; }
      .hero-kicker { margin-bottom: 9px; font-size: 12px; }
      .hero-title { font-size: clamp(26px,8vw,34px); line-height: 1.45; }
      .hero-description { margin-top: 8px; font-size: 14px; }
      .workspace-section { padding-top: 30px; }
      .section-heading { margin-bottom: 14px; }
      .workspace-options { grid-template-columns: minmax(0,1fr); gap: 12px; }
      .workspace-option { min-height: 0; padding: 21px; border-radius: 17px; }
      .option-top { margin-bottom: 15px; }
      .option-symbol { width: 46px; height: 46px; border-radius: 13px; }
      .workspace-option h3 { font-size: 19px; }
      .workspace-option p { font-size: 13px; }
      .option-action { padding-top: 19px; }
    }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; animation-duration: .01ms !important; animation-iteration-count: 1 !important; }
      .workspace-hero, .workspace-option { animation: none !important; opacity: 1; transform: none; }
    }
  </style>
</head>
<body class="hera-theme workspace-page">
  <div class="workspace-shell">
    <header class="workspace-top">
      <a class="workspace-brand" href="/BIC2_Mvp/workspace.php" aria-label="HERA — مساحات العمل">
        <img class="workspace-brand-mark" src="/BIC2_Mvp/assets/hera-icon-light.svg?v=hera-workspace-brand-20261121-1" alt="" width="43" height="43" />
        <span class="workspace-brand-copy"><strong>HERA</strong><small>HR &amp; Recruitment</small></span>
      </a>
      <nav class="top-actions" aria-label="إعدادات الحساب">
        <a class="logout-link" href="/BIC2_Mvp/logout.php"><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10 17l5-5-5-5m5 5H3"/><path d="M12 3h6a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-6"/></svg><span>تسجيل الخروج</span></a>
      </nav>
    </header>

    <main class="workspace-main" id="main-content">
      <section class="workspace-hero" aria-labelledby="workspace-title">
        <div class="hero-copy">
          <p class="hero-kicker">HERA</p>
          <h1 class="hero-title" id="workspace-title"><span>أهلًا</span> <span dir="auto"><?= $name ?></span></h1>
          <p class="hero-description">حسابك يتيح لك الوصول إلى إدارة الموارد البشرية أو التوظيف.</p>
        </div>
        <div class="hero-mark" aria-hidden="true">
          <svg viewBox="0 0 96 96" fill="none">
            <path d="M20 65V34a9 9 0 0 1 9-9h24a9 9 0 0 1 9 9v8" stroke="currentColor" stroke-width="4" stroke-linecap="round" />
            <path d="M20 48h15m-15 9h11m-11 9h8" stroke="currentColor" stroke-width="4" stroke-linecap="round" />
            <path d="m53 58 8 8 16-19" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
            <circle cx="62" cy="57" r="26" stroke="currentColor" stroke-width="2" opacity=".45" />
          </svg>
        </div>
      </section>

      <section class="workspace-section" aria-labelledby="workspace-options-title">
        <div class="section-heading">
          <h2 id="workspace-options-title">اختر مساحة العمل</h2>
        </div>
        <div class="workspace-options" aria-label="مساحات العمل">
          <a class="workspace-option workspace-option--recruitment" href="/BIC2_Mvp/launch_recruitment.php" data-workflow="recruitment">
            <div class="option-top">
              <span class="option-symbol" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="3" y="7" width="18" height="13" rx="2"/><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18m-11 0v2h4v-2"/>
                </svg>
              </span>
              <span class="option-index" aria-hidden="true">01</span>
            </div>
            <h3>إنشاء وظيفة والتوظيف</h3>
            <p>إنشاء الوظائف وإدارة المرشحين والفحص والمقابلات من منصة HERA للتوظيف.</p>
            <span class="option-action"><span>فتح مساحة التوظيف</span><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M7 17 17 7M7 7h10v10"/></svg></span></span>
          </a>

          <a class="workspace-option workspace-option--hr" href="/BIC2_Mvp/leaves.php" data-workflow="hr">
            <div class="option-top">
              <span class="option-symbol" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M16 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2m6-10a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm9-6v6m3-3h-6"/>
                </svg>
              </span>
              <span class="option-index" aria-hidden="true">02</span>
            </div>
            <h3>إدارة الموارد البشرية</h3>
            <p>متابعة الموظفين والحضور والإجازات والرواتب من نظام إدارة الموارد البشرية.</p>
            <span class="option-action"><span>فتح إدارة الموارد البشرية</span><span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M7 17 17 7M7 7h10v10"/></svg></span></span>
          </a>
        </div>
      </section>
    </main>
  </div>
  <div class="workspace-transition" aria-hidden="true"><span class="workspace-transition-mark">HERA</span></div>
  <script>
    (() => {
      const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
      let transitioning = false;
      document.querySelectorAll(".workspace-option[data-workflow]").forEach((link) => {
        link.addEventListener("click", (event) => {
          if (transitioning || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || link.target === "_blank") return;
          const target = new URL(link.href, window.location.href);
          if (target.origin !== window.location.origin) return;
          const workflow = link.dataset.workflow;
          if (!["recruitment", "hr"].includes(workflow)) return;
          event.preventDefault();
          transitioning = true;
          if (workflow === "hr") {
            try { sessionStorage.setItem("hera-workspace-entry-motion", "hr"); } catch (_) { /* Motion is optional if storage is unavailable. */ }
          }
          document.body.dataset.workspaceExit = workflow;
          window.setTimeout(() => window.location.assign(target.href), prefersReducedMotion.matches ? 0 : (workflow === "hr" ? 500 : 420));
        });
      });
    })();
  </script>
</body>
</html>
