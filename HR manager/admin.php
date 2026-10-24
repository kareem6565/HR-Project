<?php
/**
 * admin.php — Admin Dashboard with Categories & Shifts Management
 */
require_once __DIR__ . '/includes/db.php';
require_once __DIR__ . '/includes/auth.php';
require_once __DIR__ . '/includes/helpers.php';
require_once __DIR__ . '/includes/hr_platform.php';

requireHR();

$user = getCurrentUser();
$pdo  = getPDO();

// ── Pre-load data for server-side render ──────────────────────────────────────
$settings = getCompanySettings($pdo);
$today    = date('Y-m-d');

// Summary counts
$totalEmp = (int)$pdo->query("SELECT COUNT(*) FROM users WHERE role='employee'")->fetchColumn();

$stmtP = $pdo->prepare("SELECT COUNT(*) FROM attendance WHERE date=? AND status='present'");
$stmtP->execute([$today]); $cntPresent = (int)$stmtP->fetchColumn();

$stmtL = $pdo->prepare("SELECT COUNT(*) FROM attendance WHERE date=? AND status='late'");
$stmtL->execute([$today]); $cntLate = (int)$stmtL->fetchColumn();

$stmtA = $pdo->prepare("SELECT COUNT(*) FROM attendance WHERE date=? AND status='absent'");
$stmtA->execute([$today]); $cntAbsent = (int)$stmtA->fetchColumn();

$cntPresentToday = $cntPresent + $cntLate;
$cntAbsentCalc   = $totalEmp - $cntPresentToday;
?>
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>لوحة التحكم — نظام الحضور والرواتب والفئات</title>
  <meta name="description" content="لوحة تحكم المدير لإدارة الحضور والموظفين والفئات وإعدادات الشركة." />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Cairo:wght@400;500;600;700;800;900&display=swap" rel="stylesheet" />
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    * { font-family: 'Alexandria', sans-serif; }
    body {
      background: radial-gradient(ellipse at 50% 0%, #1e1b4b 0%, #080d1a 70%);
      color: #f8fafc;
      min-height: 100vh;
    }

    /* Light Mode Overrides for Admin */
    body.light-mode {
      background: #f8fafc !important;
      color: #0f172a !important;
    }
    body.light-mode .sidebar {
      background: #ffffff !important;
      border-left-color: #e2e8f0 !important;
    }
    body.light-mode header {
      background: rgba(255, 255, 255, 0.95) !important;
      border-bottom-color: #e2e8f0 !important;
    }
    body.light-mode .card, body.light-mode .card-glass {
      background: #ffffff !important;
      border-color: #e2e8f0 !important;
      box-shadow: 0 10px 30px -5px rgba(15, 23, 42, 0.06) !important;
      color: #0f172a !important;
    }
    body.light-mode h1, body.light-mode h2, body.light-mode h3, body.light-mode h4,
    body.light-mode .text-white {
      color: #0f172a !important;
    }
    body.light-mode .text-slate-400, body.light-mode .text-slate-300 {
      color: #475569 !important;
    }
    body.light-mode .bg-slate-900\/90, body.light-mode .bg-slate-950\/80, body.light-mode .bg-slate-800 {
      background-color: #f1f5f9 !important;
    }
    body.light-mode .form-input, body.light-mode select, body.light-mode input, body.light-mode textarea {
      background: #f8fafc !important;
      border-color: #cbd5e1 !important;
      color: #0f172a !important;
    }
    /* Theme Toggle High Contrast Button */
    #themeToggleBtn {
      background: rgba(255, 255, 255, 0.12);
      border: 1.5px solid rgba(255, 255, 255, 0.25);
      color: #ffffff;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }
    body.light-mode #themeToggleBtn {
      background: #ffffff !important;
      border: 1.5px solid #4f46e5 !important;
      color: #4f46e5 !important;
      box-shadow: 0 4px 14px rgba(79, 70, 229, 0.25) !important;
    }

    /* Slanted signature style */
    .skew-badge {
      transform: skewX(-8deg);
      display: inline-block;
    }
    .skew-badge-inner {
      transform: skewX(8deg);
      display: inline-block;
    }

    .sidebar {
      background: rgba(15, 23, 42, 0.95);
      backdrop-filter: blur(20px);
      border-left: 1px solid rgba(255, 255, 255, 0.08);
    }

    .card {
      background: rgba(15, 23, 42, 0.8);
      backdrop-filter: blur(16px);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 1.25rem;
      box-shadow: 0 20px 40px -15px rgba(0, 0, 0, 0.6);
      transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
    }
    .card:hover {
      border-color: rgba(99, 102, 241, 0.3);
      box-shadow: 0 25px 50px -12px rgba(79, 70, 229, 0.25);
    }

    .card-glass {
      background: rgba(255, 255, 255, 0.05);
      backdrop-filter: blur(16px);
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 1.25rem;
    }

    /* Stat cards */
    .stat-card {
      border-top: 3px solid;
      transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.3s ease;
    }
    .stat-card:hover {
      transform: translateY(-4px) scale(1.01);
      box-shadow: 0 12px 32px rgba(0, 0, 0, 0.5);
    }
    .stat-blue   { border-color: #6366f1; }
    .stat-green  { border-color: #10b981; }
    .stat-yellow { border-color: #f59e0b; }
    .stat-red    { border-color: #ef4444; }

    /* Table */
    table { border-collapse: separate; border-spacing: 0; }
    thead th { background: rgba(15, 23, 42, 0.95); font-weight: 700; color: #cbd5e1; }
    tbody tr { transition: background 0.2s ease, transform 0.15s ease; }
    tbody tr:hover { background: rgba(99, 102, 241, 0.08); }

    /* Badges */
    .badge-present { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
    .badge-late    { background: rgba(245, 158, 11, 0.15);  color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
    .badge-absent  { background: rgba(239, 68, 68, 0.15);   color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
    .badge-admin   { background: rgba(99, 102, 241, 0.15);  color: #a5b4fc; border: 1px solid rgba(99, 102, 241, 0.3); }
    .badge-emp     { background: rgba(59, 130, 246, 0.15);  color: #93c5fd; border: 1px solid rgba(59, 130, 246, 0.3); }
    .badge-cat     { background: rgba(20, 184, 166, 0.15);  color: #2dd4bf; border: 1px solid rgba(20, 184, 166, 0.3); }

    /* Buttons */
    .btn-primary {
      background: linear-gradient(135deg, #4f46e5, #3730a3);
      box-shadow: 0 4px 16px rgba(79, 70, 229, 0.45);
      transform: skewX(-4deg);
      transition: all 0.25s ease;
    }
    .btn-primary:hover {
      background: linear-gradient(135deg, #6366f1, #4f46e5);
      transform: skewX(-4deg) translateY(-2px);
      box-shadow: 0 8px 24px rgba(79, 70, 229, 0.6);
    }
    .btn-success {
      background: linear-gradient(135deg, #059669, #047857);
      transform: skewX(-4deg);
      transition: all 0.25s ease;
    }
    .btn-success:hover {
      background: linear-gradient(135deg, #10b981, #059669);
      transform: skewX(-4deg) translateY(-2px);
    }
    .btn-danger {
      background: linear-gradient(135deg, #dc2626, #b91c1c);
      transform: skewX(-4deg);
      transition: all 0.25s ease;
    }
    .btn-danger:hover {
      transform: skewX(-4deg) translateY(-2px);
      box-shadow: 0 6px 20px rgba(239, 68, 68, 0.5);
    }
    .btn-ghost {
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.15);
      transition: all 0.25s ease;
    }
    .btn-ghost:hover {
      background: rgba(255, 255, 255, 0.15);
      border-color: rgba(255, 255, 255, 0.25);
    }

    /* Modal */
    .modal-overlay { background: rgba(3, 7, 18, 0.8); backdrop-filter: blur(8px); transition: opacity 0.3s; }
    .modal-box { background: #0f172a; border: 1px solid rgba(255, 255, 255, 0.15); transition: transform 0.3s, opacity 0.3s; }

    /* Input */
    .form-input {
      background: #1e293b;
      border: 1.5px solid #334155;
      color: #ffffff;
      border-radius: 0.875rem;
      padding: 0.75rem 1.15rem;
      width: 100%;
      font-size: 0.9rem;
      font-weight: 500;
      transition: all 0.2s ease;
    }
    .form-input:focus {
      background: #0f172a;
      border-color: #6366f1;
      box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.25);
      outline: none;
    }
    .form-input::placeholder { color: #94a3b8; }
    select.form-input option { background: #0f172a; color: #ffffff; }

    /* Sidebar nav */
    .nav-item { transition: all 0.2s ease; border-right: 4px solid transparent; }
    .nav-item:hover:not(.active) { background: rgba(255, 255, 255, 0.06); }
    .nav-item.active {
      background: rgba(99, 102, 241, 0.18);
      color: #818cf8;
      border-right-color: #6366f1;
      font-weight: 700;
    }

    /* Tab panels animation */
    .tab-panel { display: none; }
    .tab-panel.active {
      display: block;
      animation: fadeInUp 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }

    @keyframes fadeInUp {
      from { opacity: 0; transform: translateY(12px); }
      to { opacity: 1; transform: translateY(0); }
    }

    /* Toast */
    #toast { position: fixed; bottom: 2rem; left: 50%; transform: translateX(-50%) translateY(100px); transition: transform .4s cubic-bezier(.34,1.56,.64,1); z-index: 9999; min-width: 300px; max-width: 90vw; }
    #toast.show { transform: translateX(-50%) translateY(0); }

    ::-webkit-scrollbar { width: 7px; }
    ::-webkit-scrollbar-track { background: #080d1a; }
    ::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }

    .spinner { animation: spin 1s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }
  </style>
  </style>
  <link rel="stylesheet" href="/BIC2_Mvp/assets/hera-brand.css" />
  <script src="/BIC2_Mvp/assets/hera-language.js" defer></script>
</head>
<body class="hera-theme min-h-screen flex">

<!-- ══════════════════════════════════ SIDEBAR ══════════════════════════════════ -->
<aside class="sidebar w-64 flex-shrink-0 flex flex-col min-h-screen sticky top-0 h-screen overflow-y-auto hidden md:flex">
  <div class="p-6 border-b border-white/05">
    <div class="flex items-center gap-3">
      <img src="/BIC2_Mvp/assets/hera-mark.svg" alt="HERA" class="w-10 h-10 object-contain rounded-xl bg-white p-1" />
      <div>
        <p class="font-bold text-white text-sm">HERA</p>
        <p class="text-xs text-slate-400">Recruitment System</p>
      </div>
    </div>
  </div>

  <div class="p-6 border-b border-white/05">
    <div class="flex items-center gap-3">
      <div class="w-12 h-12 rounded-full bg-gradient-to-br from-violet-500 to-purple-700 flex items-center justify-center text-xl font-bold text-white">
        <?= mb_substr($user['name'], 0, 1) ?>
      </div>
      <div>
        <p class="font-semibold text-white text-sm truncate"><?= htmlspecialchars($user['name']) ?></p>
        <span class="text-xs badge-admin px-2 py-0.5 rounded-full">مدير</span>
      </div>
    </div>
  </div>

  <nav class="flex-1 p-4 space-y-1">
    <button onclick="showSection('overview')"  class="nav-item active w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-right" id="nav-overview">
      <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"/></svg>
      نظرة عامة
    </button>
    <button onclick="showSection('categories')" class="nav-item w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-slate-400 text-right" id="nav-categories">
      <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/></svg>
      فئات ومجموعات العمل
    </button>
    <button onclick="showSection('attendance')" class="nav-item w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-slate-400 text-right" id="nav-attendance">
      <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg>
      سجلات الحضور
    </button>
    <button onclick="showSection('employees')" class="nav-item w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-slate-400 text-right" id="nav-employees">
      <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
      إدارة الموظفين
    </button>
    <a href="/BIC2_Mvp/leaves.php" class="nav-item w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-slate-400 text-right">الإجازات</a>
    <a href="/BIC2_Mvp/payroll.php" class="nav-item w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-slate-400 text-right">الرواتب</a>
    <a href="/BIC2_Mvp/notifications.php" class="nav-item w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-slate-400 text-right">الإشعارات</a>
    <?php if (isHRPlatformAdmin($user)): ?><a href="/BIC2_Mvp/reports.php" class="nav-item w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-slate-400 text-right">التقارير</a><?php endif; ?>
    <button onclick="showSection('settings')"  class="nav-item w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-slate-400 text-right" id="nav-settings">
      <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
      إعدادات الشركة
    </button>
  </nav>

  <div class="p-4 border-t border-white/05">
    <a href="/BIC2_Mvp/logout.php" class="flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-red-400 hover:bg-red-500/10 transition-colors w-full">
      <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/></svg>
      تسجيل الخروج
    </a>
  </div>
</aside>

<!-- ══════════════════════════════════ MAIN ══════════════════════════════════ -->
<main class="flex-1 overflow-auto">

  <!-- Top Bar -->
  <header class="sticky top-0 z-30 flex flex-col bg-slate-900/90 backdrop-blur-md border-b border-white/05">
    <div class="flex items-center justify-between px-6 py-4">
      <div>
        <h1 class="text-lg font-bold text-white" id="pageTitle">نظرة عامة</h1>
        <p class="text-xs text-slate-400"><time class="hera-localized-date" data-hera-date="<?= date('Y-m-d') ?>"><?= date('l، d F Y') ?></time></p>
      </div>
      <div class="flex items-center gap-3">
        <!-- Theme Toggle Button -->
        <button onclick="toggleTheme()" id="themeToggleBtn" class="btn-ghost rounded-xl px-3.5 py-2 text-xs font-bold text-slate-200 flex items-center gap-2 transition-all">
          <span id="themeIcon">☀️</span>
          <span id="themeText" class="hidden sm:inline">المود الفاتح</span>
        </button>

        <button onclick="refreshData()" class="btn-ghost rounded-xl px-3 py-2 text-sm text-slate-300 flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" id="refreshIcon" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
          <span class="hidden sm:inline">تحديث</span>
        </button>
        <a href="/BIC2_Mvp/logout.php" class="md:hidden btn-ghost rounded-xl px-3 py-2 text-xs text-red-400 font-semibold">خروج</a>
      </div>
    </div>

    <!-- Mobile Responsive Tabs Navigation Bar -->
    <div class="md:hidden overflow-x-auto border-t border-white/05 px-4 py-2 flex items-center gap-2 bg-slate-950/80 scrollbar-none">
      <button onclick="showSection('overview')" id="mnav-overview" class="px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap bg-blue-600/20 text-blue-300 border border-blue-500/30">📊 نظرة عامة</button>
      <button onclick="showSection('categories')" id="mnav-categories" class="px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap bg-white/05 text-slate-300">🏢 الفئات الشفتات</button>
      <button onclick="showSection('attendance')" id="mnav-attendance" class="px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap bg-white/05 text-slate-300">📅 سجلات الحضور</button>
      <button onclick="showSection('employees')" id="mnav-employees" class="px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap bg-white/05 text-slate-300">👥 إدارة الموظفين</button>
      <a href="/BIC2_Mvp/leaves.php" class="px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap bg-white/05 text-slate-300">الإجازات</a>
      <a href="/BIC2_Mvp/payroll.php" class="px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap bg-white/05 text-slate-300">الرواتب</a>
      <a href="/BIC2_Mvp/notifications.php" class="px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap bg-white/05 text-slate-300">الإشعارات</a>
      <?php if (isHRPlatformAdmin($user)): ?><a href="/BIC2_Mvp/reports.php" class="px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap bg-white/05 text-slate-300">التقارير</a><?php endif; ?>
      <button onclick="showSection('settings')" id="mnav-settings" class="px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap bg-white/05 text-slate-300">⚙️ الإعدادات</button>
    </div>
  </header>

  <div class="p-6 max-w-7xl mx-auto">

    <!-- ─────────────────────────── OVERVIEW ─────────────────────────────── -->
    <section id="section-overview" class="tab-panel active space-y-6">

      <!-- Stat Cards -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div class="card stat-card stat-blue p-5">
          <div class="flex items-center justify-between mb-3">
            <p class="text-xs text-slate-400 font-medium">إجمالي الموظفين</p>
            <div class="w-9 h-9 rounded-xl bg-blue-500/15 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
            </div>
          </div>
          <p class="text-3xl font-black text-blue-400" id="statTotal"><?= $totalEmp ?></p>
          <p class="text-xs text-slate-500 mt-1">موظف مسجّل</p>
        </div>

        <div class="card stat-card stat-green p-5">
          <div class="flex items-center justify-between mb-3">
            <p class="text-xs text-slate-400 font-medium">الحاضرون اليوم</p>
            <div class="w-9 h-9 rounded-xl bg-emerald-500/15 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            </div>
          </div>
          <p class="text-3xl font-black text-emerald-400" id="statPresent"><?= $cntPresentToday ?></p>
          <p class="text-xs text-slate-500 mt-1">حاضر + متأخر</p>
        </div>

        <div class="card stat-card stat-yellow p-5">
          <div class="flex items-center justify-between mb-3">
            <p class="text-xs text-slate-400 font-medium">المتأخرون</p>
            <div class="w-9 h-9 rounded-xl bg-amber-500/15 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            </div>
          </div>
          <p class="text-3xl font-black text-amber-400" id="statLate"><?= $cntLate ?></p>
          <p class="text-xs text-slate-500 mt-1">تجاوزوا وقت الشفت</p>
        </div>

        <div class="card stat-card stat-red p-5">
          <div class="flex items-center justify-between mb-3">
            <p class="text-xs text-slate-400 font-medium">الغائبون</p>
            <div class="w-9 h-9 rounded-xl bg-red-500/15 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            </div>
          </div>
          <p class="text-3xl font-black text-red-400" id="statAbsent"><?= $cntAbsentCalc ?></p>
          <p class="text-xs text-slate-500 mt-1">لم يسجّلوا بعد</p>
        </div>
      </div>

      <!-- Attendance feed -->
      <div class="card overflow-hidden">
        <div class="flex items-center justify-between px-6 py-4 border-b border-white/05">
          <h2 class="font-bold text-white flex items-center gap-2">
            <span class="w-2 h-2 bg-emerald-400 rounded-full animate-pulse"></span>
            سجل الحضور اليوم
          </h2>
          <p class="text-xs text-slate-500"><?= $today ?></p>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-xs text-slate-400 border-b border-white/05">
                <th class="px-5 py-3 text-right font-medium">الموظف</th>
                <th class="px-5 py-3 text-right font-medium">الفئة / الشفت</th>
                <th class="px-5 py-3 text-right font-medium">الدخول</th>
                <th class="px-5 py-3 text-right font-medium">الاستراحة</th>
                <th class="px-5 py-3 text-right font-medium">الخروج</th>
                <th class="px-5 py-3 text-right font-medium">المسافة</th>
                <th class="px-5 py-3 text-right font-medium">الحالة</th>
                <th class="px-5 py-3 text-right font-medium">الموقع</th>
              </tr>
            </thead>
            <tbody id="feedTableBody" class="divide-y divide-white/04 text-slate-300">
              <tr><td colspan="8" class="text-center py-8 text-slate-500">جارٍ التحميل...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- ─────────────────────────── CATEGORIES ───────────────────────────── -->
    <section id="section-categories" class="tab-panel space-y-6">
      <div class="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 class="font-bold text-white text-lg">فئات ومجموعات العمل (Shifts & Categories)</h2>
          <p class="text-xs text-slate-400 mt-1">تحديد مواعيد العمل، الاستراحة، مهلة الحضور، والنطاق الجغرافي لكل مجموعة.</p>
        </div>
        <button onclick="openCategoryModal()" class="btn-primary rounded-xl px-5 py-2.5 text-sm font-semibold text-white flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
          إضافة فئة جديدة
        </button>
      </div>

      <div class="card overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-xs text-slate-400 border-b border-white/05">
                <th class="px-5 py-3 text-right font-medium">اسم الفئة</th>
                <th class="px-5 py-3 text-right font-medium">مواعيد الدوام</th>
                <th class="px-5 py-3 text-right font-medium">الاستراحة (البريك)</th>
                <th class="px-5 py-3 text-right font-medium">مهلة التسجيل</th>
                <th class="px-5 py-3 text-right font-medium">النطاق الجغرافي</th>
                <th class="px-5 py-3 text-right font-medium">عدد الموظفين</th>
                <th class="px-5 py-3 text-right font-medium">إجراءات</th>
              </tr>
            </thead>
            <tbody id="categoryTableBody" class="divide-y divide-white/04 text-slate-300">
              <tr><td colspan="7" class="text-center py-8 text-slate-500">جارٍ التحميل...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- ─────────────────────────── ATTENDANCE ────────────────────────────── -->
    <section id="section-attendance" class="tab-panel space-y-6">
      <div class="card overflow-hidden">
        <div class="flex items-center justify-between px-6 py-4 border-b border-white/05">
          <h2 class="font-bold text-white">سجل الحضور الكامل — اليوم</h2>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-xs text-slate-400 border-b border-white/05">
                <th class="px-5 py-3 text-right font-medium">كود الموظف</th>
                <th class="px-5 py-3 text-right font-medium">الاسم</th>
                <th class="px-5 py-3 text-right font-medium">الفئة</th>
                <th class="px-5 py-3 text-right font-medium">الدخول</th>
                <th class="px-5 py-3 text-right font-medium">الاستراحة</th>
                <th class="px-5 py-3 text-right font-medium">الخروج</th>
                <th class="px-5 py-3 text-right font-medium">المسافة</th>
                <th class="px-5 py-3 text-right font-medium">الحالة</th>
                <th class="px-5 py-3 text-right font-medium">خريطة</th>
              </tr>
            </thead>
            <tbody id="attendanceFullBody" class="divide-y divide-white/04 text-slate-300">
              <tr><td colspan="9" class="text-center py-8 text-slate-500">جارٍ التحميل...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- ─────────────────────────── EMPLOYEES ────────────────────────────── -->
    <section id="section-employees" class="tab-panel space-y-6">
      <div class="flex flex-wrap items-center justify-between gap-4">
        <h2 class="font-bold text-white text-lg">إدارة الموظفين</h2>
        <button onclick="openEmpModal()" class="btn-primary rounded-xl px-5 py-2.5 text-sm font-semibold text-white flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
          إضافة موظف
        </button>
      </div>

      <div class="card overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-xs text-slate-400 border-b border-white/05">
                <th class="px-5 py-3 text-right font-medium">الكود</th>
                <th class="px-5 py-3 text-right font-medium">الاسم</th>
                <th class="px-5 py-3 text-right font-medium">الفئة / الشفت</th>
                <th class="px-5 py-3 text-right font-medium">الدور</th>
                <th class="px-5 py-3 text-right font-medium">الراتب الأساسي</th>
                <th class="px-5 py-3 text-right font-medium">أيام الإجازة</th>
                <th class="px-5 py-3 text-right font-medium">إجراءات</th>
              </tr>
            </thead>
            <tbody id="empTableBody" class="divide-y divide-white/04 text-slate-300">
              <tr><td colspan="7" class="text-center py-8 text-slate-500">جارٍ التحميل...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- ── SECTION: WORK SUBMISSIONS & PROGRESS ────────────────────────── -->

    <!-- ── SECTION: SETTINGS ────────────────────────────────────── -->
    <section id="section-settings" class="tab-panel">
      <div class="max-w-2xl">
        <h2 class="font-bold text-white text-lg mb-6">إعدادات الشركة الرئيسية (الافتراضية)</h2>
        <div class="card p-6 space-y-5">

          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">اسم الشركة</label>
            <input type="text" id="s_company_name" class="form-input" value="<?= htmlspecialchars($settings['company_name']) ?>" placeholder="اسم الشركة" />
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-slate-300 mb-2">خط العرض (Latitude)</label>
              <input type="number" step="0.0000001" id="s_lat" class="form-input" value="<?= $settings['center_latitude'] ?>" placeholder="24.7136000" />
            </div>
            <div>
              <label class="block text-sm font-medium text-slate-300 mb-2">خط الطول (Longitude)</label>
              <input type="number" step="0.0000001" id="s_lng" class="form-input" value="<?= $settings['center_longitude'] ?>" placeholder="46.6753000" />
            </div>
          </div>

          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">نطاق الدوام المسموح (متر)</label>
            <input type="number" min="50" max="5000" id="s_radius" class="form-input" value="<?= $settings['allowed_radius_meters'] ?>" placeholder="300" />
            <p class="text-xs text-slate-500 mt-1">النطاق الافتراضي في حال عدم تحديد فئة للموظف</p>
          </div>

          <div class="pt-2">
            <button onclick="saveSettings()" id="saveSettingsBtn" class="btn-success rounded-xl px-6 py-2.5 text-sm font-semibold text-white flex items-center gap-2">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
              حفظ الإعدادات
            </button>
          </div>
        </div>
      </div>
    </section>

  </div><!-- /max-w -->
</main>

<!-- ══════════════════════════ CATEGORY MODAL ══════════════════════════════ -->
<div id="catModal" class="fixed inset-0 z-50 hidden flex items-center justify-center p-4">
  <div class="modal-overlay absolute inset-0" onclick="closeCategoryModal()"></div>
  <div class="modal-box relative w-full max-w-xl rounded-2xl p-6 z-10 max-h-screen overflow-y-auto">
    <div class="flex items-center justify-between mb-6">
      <h3 class="text-lg font-bold text-white" id="catModalTitle">إضافة فئة عمل جديدة</h3>
      <button onclick="closeCategoryModal()" class="text-slate-400 hover:text-white transition-colors">
        <svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
      </button>
    </div>

    <form id="catForm" onsubmit="submitCategory(event)" class="space-y-4">
      <input type="hidden" id="cat_id" value="" />

      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block text-xs font-medium text-slate-400 mb-1.5">اسم الفئة / المجموعة *</label>
          <input type="text" id="c_name" class="form-input" placeholder="مثال: الشفت الصباحي أو شفت مسائي" required />
        </div>
        <div>
          <label class="block text-xs font-medium text-slate-400 mb-1.5">نوع الشفت *</label>
          <select id="c_shift_type" class="form-input font-bold">
            <option value="day">☀️ شفت صباحي (نهار)</option>
            <option value="night">🌙 شفت مسائي / ليلي (ليل)</option>
          </select>
        </div>
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block text-xs font-medium text-slate-400 mb-1.5">بداية العمل *</label>
          <input type="time" id="c_work_start" class="form-input" value="09:00" required />
        </div>
        <div>
          <label class="block text-xs font-medium text-slate-400 mb-1.5">نهاية العمل *</label>
          <input type="time" id="c_work_end" class="form-input" value="18:00" required />
        </div>
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block text-xs font-medium text-slate-400 mb-1.5">وقت بدء الاستراحة (البريك)</label>
          <input type="time" id="c_break_start" class="form-input" value="13:00" />
        </div>
        <div>
          <label class="block text-xs font-medium text-slate-400 mb-1.5">مدة الاستراحة (بالدقائق)</label>
          <input type="number" id="c_break_duration" class="form-input" value="60" min="0" max="300" />
        </div>
      </div>

      <div>
        <label class="block text-xs font-medium text-amber-400 mb-1.5">⏰ مهلة إغلاق تسجيل الحضور (بالدقائق) *</label>
        <input type="number" id="c_cutoff_minutes" class="form-input border-amber-500/40" value="60" min="5" max="480" required />
        <p class="text-xs text-slate-500 mt-1">يمنع تسجيل الدخول بعد انقضاء هذه المهلة من موعد بداية العمل.</p>
      </div>

      <div class="border-t border-white/10 pt-3">
        <p class="text-xs font-bold text-blue-400 mb-3">📍 إعدادات الموقع والجغرافيا للفئة</p>
        <div class="grid grid-cols-3 gap-3">
          <div>
            <label class="block text-xs font-medium text-slate-400 mb-1">Latitude</label>
            <input type="number" step="0.0000001" id="c_lat" class="form-input" value="<?= $settings['center_latitude'] ?>" required />
          </div>
          <div>
            <label class="block text-xs font-medium text-slate-400 mb-1">Longitude</label>
            <input type="number" step="0.0000001" id="c_lng" class="form-input" value="<?= $settings['center_longitude'] ?>" required />
          </div>
          <div>
            <label class="block text-xs font-medium text-slate-400 mb-1">النطاق (متر)</label>
            <input type="number" id="c_radius" class="form-input" value="300" min="50" required />
          </div>
        </div>
      </div>

      <div class="flex gap-3 pt-4">
        <button type="submit" id="catSubmitBtn" class="btn-primary flex-1 rounded-xl py-2.5 text-sm font-bold text-white flex items-center justify-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
          <span id="catSubmitLabel">حفظ الفئة</span>
        </button>
        <button type="button" onclick="closeCategoryModal()" class="btn-ghost rounded-xl px-5 py-2.5 text-sm font-medium text-slate-300">إلغاء</button>
      </div>
    </form>
  </div>
</div>

<!-- ══════════════════════════ ASSIGN EMPLOYEES MODAL ══════════════════════════════ -->
<div id="assignModal" class="fixed inset-0 z-50 hidden flex items-center justify-center p-4">
  <div class="modal-overlay absolute inset-0" onclick="closeAssignModal()"></div>
  <div class="modal-box relative w-full max-w-lg rounded-2xl p-6 z-10 max-h-screen overflow-y-auto">
    <div class="flex items-center justify-between mb-6 border-b border-white/10 pb-4">
      <div>
        <h3 class="text-lg font-bold text-white" id="assignModalTitle">تحديد الموظفين التابعين للفئة</h3>
        <p class="text-xs text-blue-400 mt-1" id="assignModalSub">اختر الموظفين لنقلهم إلى هذه الفئة/الشفت</p>
      </div>
      <button onclick="closeAssignModal()" class="text-slate-400 hover:text-white transition-colors">
        <svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
      </button>
    </div>

    <form id="assignForm" onsubmit="submitAssignEmployees(event)" class="space-y-4">
      <input type="hidden" id="assign_cat_id" value="" />

      <div class="flex justify-between items-center text-xs mb-2">
        <span class="text-slate-400">حدد الموظفين المراد نقلهم لهذه الفئة:</span>
        <button type="button" onclick="toggleSelectAllEmployees()" class="text-blue-400 hover:underline">تحديد / إلغاء الجميع</button>
      </div>

      <div class="space-y-2 max-h-60 overflow-y-auto p-3 rounded-xl bg-slate-900/60 border border-white/10" id="assignEmpList">
        <p class="text-xs text-slate-500 text-center py-4">جارٍ التحميل...</p>
      </div>

      <div class="flex gap-3 pt-4 border-t border-white/10">
        <button type="submit" id="assignSubmitBtn" class="btn-primary flex-1 rounded-xl py-2.5 text-sm font-bold text-white flex items-center justify-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
          حفظ التعيين والنقل
        </button>
        <button type="button" onclick="closeAssignModal()" class="btn-ghost rounded-xl px-5 py-2.5 text-sm font-medium text-slate-300">إلغاء</button>
      </div>
    </form>
  </div>
</div>


<!-- ══════════════════════════ EMPLOYEE MODAL ══════════════════════════════ -->
<div id="empModal" class="fixed inset-0 z-50 hidden flex items-center justify-center p-4">
  <div class="modal-overlay absolute inset-0" onclick="closeEmpModal()"></div>
  <div class="modal-box relative w-full max-w-lg rounded-2xl p-6 z-10 max-h-screen overflow-y-auto">
    <div class="flex items-center justify-between mb-6">
      <h3 class="text-lg font-bold text-white" id="modalTitle">إضافة موظف جديد</h3>
      <button onclick="closeEmpModal()" class="text-slate-400 hover:text-white transition-colors">
        <svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
      </button>
    </div>

    <form id="empForm" onsubmit="submitEmployee(event)" class="space-y-4">
      <input type="hidden" id="emp_id" value="" />

      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block text-xs font-medium text-slate-400 mb-1.5">كود الموظف *</label>
          <input type="text" id="f_emp_code" class="form-input" placeholder="EMP005" required />
        </div>
        <div>
          <label class="block text-xs font-medium text-slate-400 mb-1.5">الاسم الكامل *</label>
          <input type="text" id="f_name" class="form-input" placeholder="محمد أحمد" required />
        </div>
      </div>

      <div>
        <label class="block text-xs font-medium text-slate-400 mb-1.5">فئة / مجموعة العمل *</label>
        <select id="f_category_id" class="form-input">
          <option value="">-- اختر الفئة --</option>
        </select>
      </div>

      <div>
        <label class="block text-xs font-medium text-slate-400 mb-1.5">كلمة المرور <span id="passRequired">*</span></label>
        <input type="password" id="f_password" class="form-input" placeholder="••••••••" />
        <p class="text-xs text-slate-500 mt-1" id="passHint" style="display:none">اتركها فارغة للإبقاء على كلمة المرور الحالية</p>
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block text-xs font-medium text-slate-400 mb-1.5">الدور *</label>
          <select id="f_role" class="form-input">
            <option value="employee">👤 موظف عادي (Employee)</option>
            <option value="manager">👔 مدير فريق (Manager)</option>
            <option value="hr">💼 مسؤول موارد بشرية (HR)</option>
            <option value="admin">🔑 مدير النظام (Admin)</option>
          </select>
        </div>
        <div>
          <label class="block text-xs font-medium text-slate-400 mb-1.5">أيام الإجازة السنوية</label>
          <input type="number" id="f_vacation" class="form-input" value="21" min="0" max="365" />
        </div>
      </div>

      <div>
        <label class="block text-xs font-medium text-slate-400 mb-1.5">الراتب الأساسي (ريال) *</label>
        <input type="number" id="f_salary" class="form-input" placeholder="8000" min="0" step="100" required />
      </div>

      <div class="flex gap-3 pt-2">
        <button type="submit" id="empSubmitBtn" class="btn-primary flex-1 rounded-xl py-2.5 text-sm font-bold text-white flex items-center justify-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
          <span id="empSubmitLabel">إضافة الموظف</span>
        </button>
        <button type="button" onclick="closeEmpModal()" class="btn-ghost rounded-xl px-5 py-2.5 text-sm font-medium text-slate-300">إلغاء</button>
      </div>
    </form>
  </div>
</div>

<!-- Delete Confirm Modal -->
<div id="deleteModal" class="fixed inset-0 z-50 hidden flex items-center justify-center p-4">
  <div class="modal-overlay absolute inset-0" onclick="closeDeleteModal()"></div>
  <div class="modal-box relative w-full max-w-sm rounded-2xl p-6 z-10 text-center">
    <div class="w-16 h-16 bg-red-500/15 rounded-full flex items-center justify-center mx-auto mb-4">
      <svg xmlns="http://www.w3.org/2000/svg" class="w-8 h-8 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
    </div>
    <h3 class="text-lg font-bold text-white mb-2">تأكيد الحذف</h3>
    <p class="text-sm text-slate-400 mb-6" id="deleteModalText">هل أنت متأكد من الحذف؟</p>
    <input type="hidden" id="deleteTargetId" />
    <input type="hidden" id="deleteTargetType" />
    <div class="flex gap-3">
      <button onclick="confirmDelete()" class="btn-danger flex-1 rounded-xl py-2.5 text-sm font-bold text-white">نعم، احذف</button>
      <button onclick="closeDeleteModal()" class="btn-ghost flex-1 rounded-xl py-2.5 text-sm font-medium text-slate-300">إلغاء</button>
    </div>
  </div>
</div>

<!-- Toast -->
<div id="toast" class="card px-6 py-4 flex items-center gap-4 shadow-2xl">
  <div id="toastIcon" class="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 text-xl bg-emerald-500"></div>
  <div>
    <p id="toastTitle" class="font-bold text-white text-sm"></p>
    <p id="toastSub" class="text-xs text-slate-400 mt-0.5"></p>
  </div>
</div>

<!-- ══════════════════════════════════ JS ══════════════════════════════════ -->
<script>
// ── Section Navigation ─────────────────────────────────────────────────────────
const SECTIONS = ['overview','categories','attendance','employees','settings'];
const TITLES   = { overview:'نظرة عامة', categories:'فئات ومجموعات العمل', attendance:'سجلات الحضور', employees:'إدارة الموظفين', settings:'إعدادات الشركة' };
let globalCategories = [];

function showSection(name) {
  SECTIONS.forEach(s => {
    document.getElementById('section-' + s).classList.toggle('active', s === name);
    
    // Desktop sidebar nav
    const nav = document.getElementById('nav-' + s);
    if (nav) {
      nav.classList.toggle('active', s === name);
      nav.classList.toggle('text-slate-400', s !== name);
    }

    // Mobile topbar nav
    const mnav = document.getElementById('mnav-' + s);
    if (mnav) {
      if (s === name) {
        mnav.className = "px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap bg-blue-600/20 text-blue-300 border border-blue-500/30";
      } else {
        mnav.className = "px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap bg-white/05 text-slate-300";
      }
    }
  });
  document.getElementById('pageTitle').textContent = TITLES[name] || '';
  if (name === 'categories') loadCategories();
  if (name === 'attendance') loadAttendanceFull();
  if (name === 'employees')  { loadCategoriesDropdown(); loadEmployees(); }
}

// ── Toast ──────────────────────────────────────────────────────────────────────
function showToast(icon, title, sub, colorClass = 'bg-emerald-500') {
  const t = document.getElementById('toast');
  document.getElementById('toastIcon').textContent = icon;
  document.getElementById('toastIcon').className   = `w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 text-xl ${colorClass}`;
  document.getElementById('toastTitle').textContent = title;
  document.getElementById('toastSub').textContent   = sub;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 4000);
}

// ── Refresh ────────────────────────────────────────────────────────────────────
function refreshData() {
  const icon = document.getElementById('refreshIcon');
  icon.classList.add('spinner');
  loadFeed();
  setTimeout(() => icon.classList.remove('spinner'), 1000);
}

// ── Badges ─────────────────────────────────────────────────────────────────────
const statusMap = {
  present: ['badge-present','حاضر'],
  late:    ['badge-late','متأخر'],
  absent:  ['badge-absent','غائب'],
};
function statusBadge(s) {
  const [cls, label] = statusMap[s] || ['text-slate-400', s];
  return `<span class="text-xs font-medium px-2.5 py-1 rounded-full ${cls}">${label}</span>`;
}

// ── Load Today's Feed ──────────────────────────────────────────────────────────
function loadFeed() {
  fetch('/BIC2_Mvp/api/attendance.php?action=today_all')
    .then(r => r.json())
    .then(data => {
      const tbody = document.getElementById('feedTableBody');
      if (!data.success || !data.records.length) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center py-8 text-slate-500">لا توجد سجلات حضور لهذا اليوم.</td></tr>`;
        return;
      }
      tbody.innerHTML = data.records.map(r => {
        const mapLink = (r.lat_in && r.lng_in)
          ? `<a href="https://www.google.com/maps?q=${r.lat_in},${r.lng_in}" target="_blank" class="text-blue-400 hover:text-blue-300 text-xs underline">عرض</a>`
          : '—';
        const breakTime = r.break_start_time
          ? `<span class="text-xs font-mono text-cyan-400">${r.break_start_time.substring(0,5)} - ${r.break_end_time ? r.break_end_time.substring(0,5) : 'مستمر'}</span>`
          : '—';

        return `<tr>
          <td class="px-5 py-3">
            <div class="font-medium text-white">${r.name}</div>
            <div class="text-xs text-slate-500">${r.emp_code}</div>
          </td>
          <td class="px-5 py-3"><span class="badge-cat text-xs px-2 py-0.5 rounded-full">${r.category_name || 'عام'}</span></td>
          <td class="px-5 py-3 font-mono text-emerald-400">${r.check_in_time  ? r.check_in_time.substring(0,5)  : '—'}</td>
          <td class="px-5 py-3">${breakTime}</td>
          <td class="px-5 py-3 font-mono text-amber-400">${r.check_out_time ? r.check_out_time.substring(0,5) : '—'}</td>
          <td class="px-5 py-3 text-slate-400">${r.distance_in_meters ? r.distance_in_meters + ' م' : '—'}</td>
          <td class="px-5 py-3">${statusBadge(r.status)}</td>
          <td class="px-5 py-3">${mapLink}</td>
        </tr>`;
      }).join('');
    });
}

// ── Categories CRUD ────────────────────────────────────────────────────────────
function loadCategories() {
  fetch('/BIC2_Mvp/api/categories.php?action=list')
    .then(r => r.json())
    .then(data => {
      const tbody = document.getElementById('categoryTableBody');
      if (!data.success || !data.categories.length) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center py-8 text-slate-500">لا توجد فئات عمل مضافة.</td></tr>`;
        return;
      }
      globalCategories = data.categories;
      tbody.innerHTML = data.categories.map(c => {
        const isNight = (c.shift_type === 'night' || c.work_end_time < c.work_start_time);
        const shiftBadge = isNight 
          ? `<span class="inline-block mt-1 text-[10px] font-bold px-2.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">🌙 شفت مسائي / ليلي</span>` 
          : `<span class="inline-block mt-1 text-[10px] font-bold px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30">☀️ شفت صباحي</span>`;

        return `<tr>
          <td class="px-5 py-3 font-bold text-white">
            <div>${c.name}</div>
            ${shiftBadge}
          </td>
          <td class="px-5 py-3 font-mono text-emerald-400 text-xs">${c.work_start_time.substring(0,5)} - ${c.work_end_time.substring(0,5)}</td>
          <td class="px-5 py-3 text-xs text-cyan-300">${c.break_start_time ? c.break_start_time.substring(0,5) : '—'} (${c.break_duration_minutes} دقيقة)</td>
          <td class="px-5 py-3 text-xs text-amber-400 font-semibold">${c.cutoff_minutes} دقيقة بعد الدوام</td>
          <td class="px-5 py-3 text-xs text-slate-400">${c.allowed_radius_meters} متر</td>
          <td class="px-5 py-3 font-bold text-blue-400">${c.employee_count} موظف</td>
          <td class="px-5 py-3">
            <div class="flex gap-2">
              <button onclick='openAssignModal(${c.id}, "${c.name}")' class="btn-ghost rounded-lg px-3 py-1.5 text-xs text-purple-300 hover:text-purple-200">👥 تعيين الموظفين</button>
              <button onclick='editCategory(${JSON.stringify(c)})' class="btn-ghost rounded-lg px-3 py-1.5 text-xs text-blue-400">تعديل</button>
              <button onclick="openDeleteModal(${c.id}, 'category')" class="btn-ghost rounded-lg px-3 py-1.5 text-xs text-red-400">حذف</button>
            </div>
          </td>
        </tr>`;
      }).join('');
    });
}

function loadCategoriesDropdown() {
  fetch('/BIC2_Mvp/api/categories.php?action=list')
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        globalCategories = data.categories;
        const sel = document.getElementById('f_category_id');
        sel.innerHTML = '<option value="">-- اختر الفئة --</option>' + 
          data.categories.map(c => `<option value="${c.id}">${c.name} (${c.shift_type === 'night' ? '🌙' : '☀️'} ${c.work_start_time.substring(0,5)} - ${c.work_end_time.substring(0,5)})</option>`).join('');
      }
    });
}

function openCategoryModal() {
  document.getElementById('catModalTitle').textContent = 'إضافة فئة عمل جديدة';
  document.getElementById('cat_id').value = '';
  document.getElementById('c_name').value = '';
  document.getElementById('c_shift_type').value = 'day';
  document.getElementById('c_work_start').value = '09:00';
  document.getElementById('c_work_end').value = '18:00';
  document.getElementById('c_break_start').value = '13:00';
  document.getElementById('c_break_duration').value = '60';
  document.getElementById('c_cutoff_minutes').value = '60';
  document.getElementById('catModal').classList.remove('hidden');
}

function editCategory(c) {
  document.getElementById('catModalTitle').textContent = 'تعديل فئة العمل';
  document.getElementById('cat_id').value = c.id;
  document.getElementById('c_name').value = c.name;
  document.getElementById('c_shift_type').value = c.shift_type || (c.work_end_time < c.work_start_time ? 'night' : 'day');
  document.getElementById('c_work_start').value = c.work_start_time.substring(0,5);
  document.getElementById('c_work_end').value = c.work_end_time.substring(0,5);
  document.getElementById('c_break_start').value = c.break_start_time ? c.break_start_time.substring(0,5) : '13:00';
  document.getElementById('c_break_duration').value = c.break_duration_minutes;
  document.getElementById('c_cutoff_minutes').value = c.cutoff_minutes;
  document.getElementById('c_lat').value = c.center_latitude;
  document.getElementById('c_lng').value = c.center_longitude;
  document.getElementById('c_radius').value = c.allowed_radius_meters;
  document.getElementById('catModal').classList.remove('hidden');
}

function closeCategoryModal() {
  document.getElementById('catModal').classList.add('hidden');
}

function submitCategory(e) {
  e.preventDefault();
  const id = document.getElementById('cat_id').value;
  const isEdit = !!id;

  const payload = {
    action: isEdit ? 'update' : 'create',
    name: document.getElementById('c_name').value,
    shift_type: document.getElementById('c_shift_type').value,
    work_start_time: document.getElementById('c_work_start').value + ':00',
    work_end_time: document.getElementById('c_work_end').value + ':00',
    break_start_time: document.getElementById('c_break_start').value + ':00',
    break_duration_minutes: document.getElementById('c_break_duration').value,
    cutoff_minutes: document.getElementById('c_cutoff_minutes').value,
    center_latitude: document.getElementById('c_lat').value,
    center_longitude: document.getElementById('c_lng').value,
    allowed_radius_meters: document.getElementById('c_radius').value,
  };
  if (isEdit) payload.id = id;

  fetch('/BIC2_Mvp/api/categories.php', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      showToast('✅', data.message, '');
      closeCategoryModal();
      loadCategories();
    } else {
      showToast('❌', 'خطأ', data.message, 'bg-red-500');
    }
  });
}

// ── Bulk Assign Employees Modal Functions ──────────────────────────────────────
function openAssignModal(catId, catName) {
  document.getElementById('assign_cat_id').value = catId;
  document.getElementById('assignModalSub').textContent = `الفئة الحالية: ${catName}`;
  document.getElementById('assignEmpList').innerHTML = '<p class="text-xs text-slate-500 text-center py-4">جارٍ التحميل...</p>';
  document.getElementById('assignModal').classList.remove('hidden');

  fetch('/BIC2_Mvp/api/employees.php?action=list')
    .then(r => r.json())
    .then(data => {
      if (!data.success || !data.employees.length) {
        document.getElementById('assignEmpList').innerHTML = '<p class="text-xs text-slate-500 text-center py-4">لا يوجد موظفون بالسيستم.</p>';
        return;
      }
      document.getElementById('assignEmpList').innerHTML = data.employees.map(emp => {
        const checked = (emp.category_id == catId) ? 'checked' : '';
        const currentCat = emp.category_name ? `<span class="text-[10px] text-teal-400">(${emp.category_name})</span>` : '<span class="text-[10px] text-slate-500">(غير محدد)</span>';
        return `
          <label class="flex items-center justify-between p-2 rounded-lg hover:bg-white/05 cursor-pointer border border-white/05">
            <div class="flex items-center gap-3">
              <input type="checkbox" name="emp_assign" value="${emp.id}" ${checked} class="w-4 h-4 rounded text-blue-600 bg-slate-800 border-slate-700">
              <div>
                <p class="text-sm font-semibold text-white">${emp.name}</p>
                <p class="text-xs text-slate-400 font-mono">${emp.emp_code} ${currentCat}</p>
              </div>
            </div>
          </label>
        `;
      }).join('');
    });
}

function toggleSelectAllEmployees() {
  const checkboxes = document.querySelectorAll('input[name="emp_assign"]');
  const allChecked = Array.from(checkboxes).every(cb => cb.checked);
  checkboxes.forEach(cb => cb.checked = !allChecked);
}

function closeAssignModal() {
  document.getElementById('assignModal').classList.add('hidden');
}

function submitAssignEmployees(e) {
  e.preventDefault();
  const catId = document.getElementById('assign_cat_id').value;
  const checkboxes = document.querySelectorAll('input[name="emp_assign"]:checked');
  const userIds = Array.from(checkboxes).map(cb => cb.value);

  fetch('/BIC2_Mvp/api/categories.php', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      action: 'assign_employees',
      category_id: catId,
      user_ids: userIds,
    }),
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      showToast('✅', data.message, '');
      closeAssignModal();
      loadCategories();
      loadEmployees();
    } else {
      showToast('❌', 'خطأ', data.message, 'bg-red-500');
    }
  });
}

// ── Load Attendance Full ───────────────────────────────────────────────────────
function loadAttendanceFull() {
  fetch('/BIC2_Mvp/api/attendance.php?action=today_all')
    .then(r => r.json())
    .then(data => {
      const tbody = document.getElementById('attendanceFullBody');
      if (!data.success || !data.records.length) {
        tbody.innerHTML = `<tr><td colspan="9" class="text-center py-8 text-slate-500">لا توجد سجلات لهذا اليوم.</td></tr>`;
        return;
      }
      tbody.innerHTML = data.records.map(r => {
        const mapLink = (r.lat_in && r.lng_in)
          ? `<a href="https://www.google.com/maps?q=${r.lat_in},${r.lng_in}" target="_blank" class="text-blue-400 hover:text-blue-300 underline text-xs">📍 عرض</a>`
          : '—';
        const breakTime = r.break_start_time
          ? `<span class="text-xs font-mono text-cyan-400">${r.break_start_time.substring(0,5)} - ${r.break_end_time ? r.break_end_time.substring(0,5) : 'مستمر'}</span>`
          : '—';

        return `<tr>
          <td class="px-5 py-3 font-mono text-xs text-slate-400">${r.emp_code}</td>
          <td class="px-5 py-3 font-medium text-white">${r.name}</td>
          <td class="px-5 py-3"><span class="badge-cat text-xs px-2 py-0.5 rounded-full">${r.category_name || 'عام'}</span></td>
          <td class="px-5 py-3 font-mono text-emerald-400">${r.check_in_time  ? r.check_in_time.substring(0,5)  : '—'}</td>
          <td class="px-5 py-3">${breakTime}</td>
          <td class="px-5 py-3 font-mono text-amber-400">${r.check_out_time ? r.check_out_time.substring(0,5) : '—'}</td>
          <td class="px-5 py-3 text-slate-400">${r.distance_in_meters ? r.distance_in_meters + ' م' : '—'}</td>
          <td class="px-5 py-3">${statusBadge(r.status)}</td>
          <td class="px-5 py-3">${mapLink}</td>
        </tr>`;
      }).join('');
    });
}

// ── Load Employees ─────────────────────────────────────────────────────────────
function loadEmployees() {
  fetch('/BIC2_Mvp/api/employees.php?action=list')
    .then(r => r.json())
    .then(data => {
      const tbody = document.getElementById('empTableBody');
      if (!data.success || !data.employees.length) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center py-8 text-slate-500">لا يوجد موظفون.</td></tr>`;
        return;
      }
      tbody.innerHTML = data.employees.map(e => {
        let roleBadge = `<span class="text-xs font-medium px-2.5 py-1 rounded-full badge-emp">موظف</span>`;
        if (e.role === 'admin') {
          roleBadge = `<span class="text-xs font-medium px-2.5 py-1 rounded-full badge-admin">مدير</span>`;
        } else if (e.role === 'hr') {
          roleBadge = `<span class="text-xs font-medium px-2.5 py-1 rounded-full bg-pink-500/15 text-pink-300 border border-pink-500/30">HR</span>`;
        } else if (e.role === 'manager') {
          roleBadge = `<span class="text-xs font-medium px-2.5 py-1 rounded-full bg-violet-500/15 text-violet-300 border border-violet-500/30">Manager</span>`;
        }
        return `<tr>
          <td class="px-5 py-3 font-mono text-xs text-slate-400">${e.emp_code}</td>
          <td class="px-5 py-3 font-medium text-white">${e.name}</td>
          <td class="px-5 py-3"><span class="badge-cat text-xs px-2.5 py-1 rounded-full">${e.category_name || 'غير محدد'}</span></td>
          <td class="px-5 py-3">${roleBadge}</td>
          <td class="px-5 py-3 text-emerald-400 font-semibold">${parseFloat(e.basic_salary).toLocaleString('ar')} ر.س</td>
          <td class="px-5 py-3 text-blue-400">${e.yearly_vacation_days} يوم</td>
          <td class="px-5 py-3">
            <div class="flex gap-2">
              <a href="/BIC2_Mvp/profile.php?id=${e.id}" class="btn-ghost rounded-lg px-3 py-1.5 text-xs text-purple-300 hover:text-purple-200">
                👤 البروفايل
              </a>
              <button onclick='editEmployee(${JSON.stringify(e)})' class="btn-ghost rounded-lg px-3 py-1.5 text-xs text-blue-400 hover:text-blue-300">
                تعديل
              </button>
              <button onclick="openDeleteModal(${e.id}, 'employee')" class="btn-ghost rounded-lg px-3 py-1.5 text-xs text-red-400 hover:text-red-300">
                حذف
              </button>
            </div>
          </td>
        </tr>`;
      }).join('');
    });
}

// ── Employee Modal ─────────────────────────────────────────────────────────────
function openEmpModal() {
  loadCategoriesDropdown();
  document.getElementById('modalTitle').textContent   = 'إضافة موظف جديد';
  document.getElementById('empSubmitLabel').textContent = 'إضافة الموظف';
  document.getElementById('emp_id').value    = '';
  document.getElementById('f_emp_code').value= '';
  document.getElementById('f_name').value    = '';
  document.getElementById('f_category_id').value = '';
  document.getElementById('f_password').value= '';
  document.getElementById('f_role').value    = 'employee';
  document.getElementById('f_salary').value  = '';
  document.getElementById('f_vacation').value= '21';
  document.getElementById('passRequired').style.display = '';
  document.getElementById('passHint').style.display     = 'none';
  document.getElementById('f_password').required = true;
  document.getElementById('empModal').classList.remove('hidden');
}

function editEmployee(e) {
  loadCategoriesDropdown();
  document.getElementById('modalTitle').textContent    = 'تعديل بيانات الموظف';
  document.getElementById('empSubmitLabel').textContent= 'حفظ التعديلات';
  document.getElementById('emp_id').value    = e.id;
  document.getElementById('f_emp_code').value= e.emp_code;
  document.getElementById('f_name').value    = e.name;
  setTimeout(() => { document.getElementById('f_category_id').value = e.category_id || ''; }, 100);
  document.getElementById('f_password').value= '';
  document.getElementById('f_role').value    = e.role;
  document.getElementById('f_salary').value  = e.basic_salary;
  document.getElementById('f_vacation').value= e.yearly_vacation_days;
  document.getElementById('passRequired').style.display = 'none';
  document.getElementById('passHint').style.display     = '';
  document.getElementById('f_password').required = false;
  document.getElementById('empModal').classList.remove('hidden');
}

function closeEmpModal() {
  document.getElementById('empModal').classList.add('hidden');
}

function submitEmployee(e) {
  e.preventDefault();
  const id = document.getElementById('emp_id').value;
  const isEdit = !!id;

  const payload = {
    action:               isEdit ? 'update' : 'create',
    emp_code:             document.getElementById('f_emp_code').value,
    name:                 document.getElementById('f_name').value,
    category_id:          document.getElementById('f_category_id').value,
    password:             document.getElementById('f_password').value,
    role:                 document.getElementById('f_role').value,
    basic_salary:         document.getElementById('f_salary').value,
    yearly_vacation_days: document.getElementById('f_vacation').value,
  };
  if (isEdit) payload.id = id;

  fetch('/BIC2_Mvp/api/employees.php', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      showToast('✅', data.message, '');
      closeEmpModal();
      loadEmployees();
    } else {
      showToast('❌', 'خطأ', data.message, 'bg-red-500');
    }
  });
}

// ── Delete Modal ───────────────────────────────────────────────────────────────
function openDeleteModal(id, type = 'employee') {
  document.getElementById('deleteTargetId').value = id;
  document.getElementById('deleteTargetType').value = type;
  document.getElementById('deleteModalText').textContent = type === 'category' 
    ? 'هل أنت متأكد من حذف هذه الفئة؟ سيتم إلغاء تعيينها للموظفين التابعين لها.' 
    : 'هل أنت متأكد من حذف هذا الموظف؟ سيتم حذف جميع سجلاته أيضاً ولا يمكن التراجع.';
  document.getElementById('deleteModal').classList.remove('hidden');
}
function closeDeleteModal() {
  document.getElementById('deleteModal').classList.add('hidden');
}
function confirmDelete() {
  const id = document.getElementById('deleteTargetId').value;
  const type = document.getElementById('deleteTargetType').value;

  const url = type === 'category' ? '/BIC2_Mvp/api/categories.php' : '/BIC2_Mvp/api/employees.php';

  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'delete', id }),
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      showToast('🗑️', data.message, '');
      closeDeleteModal();
      if (type === 'category') loadCategories(); else loadEmployees();
    } else {
      showToast('❌', 'خطأ', data.message, 'bg-red-500');
    }
  });
}

// ── Settings ───────────────────────────────────────────────────────────────────
function saveSettings() {
  fetch('/BIC2_Mvp/api/settings.php', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      company_name:           document.getElementById('s_company_name').value,
      center_latitude:        document.getElementById('s_lat').value,
      center_longitude:       document.getElementById('s_lng').value,
      allowed_radius_meters:  document.getElementById('s_radius').value,
    }),
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      showToast('✅', data.message, '');
    } else {
      showToast('❌', 'خطأ في الحفظ', data.message, 'bg-red-500');
    }
  });
}

// ── Theme Switcher ─────────────────────────────────────────────────────────────
function initTheme() {
  const saved = localStorage.getItem('theme');
  if (saved === 'light') {
    document.body.classList.add('light-mode');
    updateThemeUI(true);
  }
}
function toggleTheme() {
  const isLight = document.body.classList.toggle('light-mode');
  localStorage.setItem('theme', isLight ? 'light' : 'dark');
  updateThemeUI(isLight);
}
function updateThemeUI(isLight) {
  const icon = document.getElementById('themeIcon');
  const text = document.getElementById('themeText');
  if (icon) icon.textContent = isLight ? '🌙' : '☀️';
  if (text) text.textContent = isLight ? 'المود الداكن' : 'المود الفاتح';
}

// ── Init ───────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', initTheme);
loadFeed();
setInterval(loadFeed, 60000);
</script>
</body>
</html>
