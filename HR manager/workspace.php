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
  <title>اختيار مساحة العمل — HERA</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800;900&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="/BIC2_Mvp/assets/hera-brand.css" />
  <script src="/BIC2_Mvp/assets/hera-language.js" defer></script>
  <style>
    * { box-sizing: border-box; font-family: Cairo, sans-serif; }
    body { margin: 0; min-height: 100vh; color: #292C2A; background: #FAF7F2; }
    .workspace { width: min(960px, calc(100% - 32px)); margin: 0 auto; padding: 44px 0; }
    .top { display:flex; justify-content:space-between; align-items:center; gap:16px; margin-bottom:56px; }
    .top img { width: 172px; }
    .top a { color:#1B3A3A; font-weight:700; text-decoration:none; }
    h1 { margin:0 0 8px; font-size:clamp(27px,4vw,40px); color:#1B3A3A; }
    .intro { margin:0 0 30px; color:#66736F; }
    .options { display:grid; grid-template-columns:repeat(auto-fit,minmax(270px,1fr)); gap:18px; }
    .option { display:flex; flex-direction:column; align-items:flex-start; min-height:250px; padding:26px; border:1px solid #E2E5E3; border-radius:22px; background:#fff; color:#292C2A; text-decoration:none; box-shadow:0 10px 28px rgba(27,58,58,.07); transition:transform .18s,border-color .18s; }
    .option:hover { transform:translateY(-3px); border-color:#6FA8B8; }
    .symbol { display:grid; place-items:center; width:52px; height:52px; margin-bottom:22px; border-radius:16px; background:#E9D98A; color:#1B3A3A; font-size:25px; }
    .option h2 { margin:0 0 9px; color:#1B3A3A; font-size:21px; }
    .option p { margin:0; color:#66736F; line-height:1.8; }
    .action { margin-top:auto; padding-top:22px; color:#1B3A3A; font-weight:800; }
    @media(max-width:540px){.top{margin-bottom:38px}.top img{width:140px}}
  </style>
</head>
<body class="hera-theme">
  <main class="workspace">
    <header class="top">
      <img src="/BIC2_Mvp/assets/hera-logo.svg" alt="HERA" />
      <a href="/BIC2_Mvp/logout.php">تسجيل الخروج</a>
    </header>
    <h1>أهلًا <?= $name ?>، اختر مساحة العمل</h1>
    <p class="intro">حسابك يتيح لك الوصول إلى إدارة الموارد البشرية أو التوظيف.</p>
    <section class="options" aria-label="مساحات العمل">
      <a class="option" href="/BIC2_Mvp/launch_recruitment.php">
        <span class="symbol" aria-hidden="true">✦</span>
        <h2>إنشاء وظيفة والتوظيف</h2>
        <p>إنشاء الوظائف وإدارة المرشحين والفحص والمقابلات من منصة HERA للتوظيف.</p>
        <span class="action">فتح مساحة التوظيف ←</span>
      </a>
      <a class="option" href="/BIC2_Mvp/leaves.php">
        <span class="symbol" aria-hidden="true">◷</span>
        <h2>إدارة الموارد البشرية</h2>
        <p>متابعة الموظفين والحضور والإجازات والرواتب من نظام إدارة الموارد البشرية.</p>
        <span class="action">فتح إدارة الموارد البشرية ←</span>
      </a>
    </section>
  </main>
</body>
</html>
