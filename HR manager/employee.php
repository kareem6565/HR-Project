<?php
/**
 * employee.php — Employee Self-Service Portal with Category & Break Support
 */
require_once __DIR__ . '/includes/db.php';
require_once __DIR__ . '/includes/auth.php';
require_once __DIR__ . '/includes/helpers.php';

requireLogin();

$user = getCurrentUser();
$pdo  = getPDO();

// Load today's record, or an open record from yesterday for a cross-midnight shift.
$today    = date('Y-m-d');
$yesterday = date('Y-m-d', strtotime('-1 day'));
$stmtDay  = $pdo->prepare(
    "SELECT * FROM attendance
     WHERE user_id = ? AND (date = ? OR (date = ? AND check_out_time IS NULL))
     ORDER BY date DESC LIMIT 1"
);
$stmtDay->execute([$user['id'], $today, $yesterday]);
$todayRec = $stmtDay->fetch();

// Determine button states
$hasCheckedIn  = $todayRec && $todayRec['check_in_time'] !== null;
$hasCheckedOut = $todayRec && $todayRec['check_out_time'] !== null;
$hasBreakStart = $todayRec && $todayRec['break_start_time'] !== null;
$hasBreakEnd   = $todayRec && $todayRec['break_end_time'] !== null;

// Load full user row & category
$stmtUser = $pdo->prepare(
    "SELECT u.*, c.name AS category_name, c.work_start_time, c.work_end_time,
            c.break_start_time, c.break_duration_minutes, c.cutoff_minutes,
            c.center_latitude AS cat_lat, c.center_longitude AS cat_lng, c.allowed_radius_meters AS cat_radius
     FROM users u
     LEFT JOIN categories c ON c.id = u.category_id
     WHERE u.id = ?"
);
$stmtUser->execute([$user['id']]);
$fullUser = $stmtUser->fetch();

// Fallback to company_settings if no category
$settings = getCompanySettings($pdo);
$catLat    = $fullUser['cat_lat'] ?? $settings['center_latitude'];
$catLng    = $fullUser['cat_lng'] ?? $settings['center_longitude'];
$catRadius = $fullUser['cat_radius'] ?? $settings['allowed_radius_meters'];
$catName   = $fullUser['category_name'] ?? 'عام';
$workStart = $fullUser['work_start_time'] ?? '09:00:00';
$workEnd   = $fullUser['work_end_time'] ?? '18:00:00';
$breakStart= $fullUser['break_start_time'] ?? '13:00:00';
$breakDur  = $fullUser['break_duration_minutes'] ?? 60;
$cutoffMin = $fullUser['cutoff_minutes'] ?? 60;

// Current time and time window validations for active/dimmed button states
$now = date('H:i:s');
$isNightShift = ($workEnd < $workStart || $workStart === '00:00:00' || $workStart >= '18:00:00');

// Can start break?
if ($isNightShift) {
    if ($workStart === '00:00:00') {
        $canStartBreak = $hasCheckedIn && !$hasCheckedOut && !$hasBreakStart && ($now >= $breakStart && $now <= $workEnd);
    } else {
        $canStartBreak = $hasCheckedIn && !$hasCheckedOut && !$hasBreakStart && ($now >= $breakStart || $now < $workEnd);
    }
} else {
    $canStartBreak = $hasCheckedIn && !$hasCheckedOut && !$hasBreakStart && ($now >= $breakStart && $now <= $workEnd);
}

// Can checkout?
if ($isNightShift) {
    if ($workStart === '00:00:00') {
        // For midnight shift 00:00 to 09:00, checkout is valid in the morning from 09:00 to 14:00
        $canCheckout = $hasCheckedIn && !$hasCheckedOut && ($now >= $workEnd && $now <= '14:00:00');
    } else {
        $canCheckout = $hasCheckedIn && !$hasCheckedOut && ($now >= $workEnd && $now < $workStart);
    }
} else {
    $canCheckout = $hasCheckedIn && !$hasCheckedOut && ($now >= $workEnd);
}
?>
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>بوابة الموظف — <?= htmlspecialchars($user['name']) ?></title>
  <meta name="description" content="بوابة الموظف لتسجيل الحضور والانصراف والاستراحة." />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Cairo:wght@400;500;600;700;800;900&display=swap" rel="stylesheet" />
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    * { font-family: 'Cairo', sans-serif; }
    body { background: #080c14; color: #f8fafc; }

    /* Light Mode Overrides */
    body.light-mode {
      background-color: #f8fafc !important;
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

    .sidebar { background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%); border-left: 1px solid rgba(255,255,255,0.06); }
    .card { background: rgba(30,41,59,0.8); border: 1px solid rgba(255,255,255,0.07); border-radius: 1rem; }
    .card-glass { background: rgba(255,255,255,0.04); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.08); border-radius: 1rem; }

    .btn-checkin {
      background: linear-gradient(135deg, #10b981, #059669);
      box-shadow: 0 8px 32px rgba(16,185,129,0.4);
      transition: all 0.3s ease;
    }
    .btn-checkin:hover { box-shadow: 0 12px 40px rgba(16,185,129,0.6); transform: translateY(-2px) scale(1.02); }
    
    .btn-checkout {
      background: linear-gradient(135deg, #f59e0b, #d97706);
      box-shadow: 0 8px 32px rgba(245,158,11,0.4);
      transition: all 0.3s ease;
    }
    .btn-checkout:hover { box-shadow: 0 12px 40px rgba(245,158,11,0.6); transform: translateY(-2px) scale(1.02); }
    
    .btn-break {
      background: linear-gradient(135deg, #06b6d4, #0891b2);
      box-shadow: 0 6px 20px rgba(6,182,212,0.3);
      transition: all 0.3s ease;
    }
    .btn-break:hover { box-shadow: 0 8px 25px rgba(6,182,212,0.5); transform: translateY(-1px); }

    .btn-done {
      background: rgba(100,116,139,0.3);
      border: 1px solid rgba(100,116,139,0.4);
      cursor: not-allowed;
    }

    .pulse-ring {
      position: absolute; inset: -8px; border-radius: 50%;
      border: 3px solid rgba(16,185,129,0.5);
      animation: pulseRing 2s ease-out infinite;
    }
    @keyframes pulseRing {
      0% { transform: scale(1); opacity: 1; }
      100% { transform: scale(1.4); opacity: 0; }
    }

    .gps-spinner { animation: spin 1s linear infinite; }
    @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

    #toast {
      position: fixed; bottom: 2rem; left: 50%; transform: translateX(-50%) translateY(100px);
      transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
      z-index: 9999; min-width: 300px; max-width: 90vw;
    }
    #toast.show { transform: translateX(-50%) translateY(0); }

    .badge-present { background: rgba(16,185,129,0.15); color: #34d399; border: 1px solid rgba(16,185,129,0.3); }
    .badge-late    { background: rgba(245,158,11,0.15);  color: #fbbf24; border: 1px solid rgba(245,158,11,0.3); }
    .badge-absent  { background: rgba(239,68,68,0.15);   color: #f87171; border: 1px solid rgba(239,68,68,0.3); }

    table { border-collapse: separate; border-spacing: 0; }
    thead th { background: rgba(15,23,42,0.8); }
    tbody tr { transition: background 0.2s; }
    tbody tr:hover { background: rgba(255,255,255,0.03); }

    .nav-item.active { background: rgba(59,130,246,0.15); color: #60a5fa; border-right: 3px solid #3b82f6; }
    .nav-item { transition: all 0.2s; }
    .nav-item:hover:not(.active) { background: rgba(255,255,255,0.05); }

    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: #0f172a; }
    ::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }

    .stat-green { border-top: 3px solid #10b981; }
    .stat-blue  { border-top: 3px solid #3b82f6; }
    .stat-yellow{ border-top: 3px solid #f59e0b; }
    .stat-cyan  { border-top: 3px solid #06b6d4; }

    /* Telegram Floating Button */
    .telegram-btn {
      position: fixed;
      bottom: 1.5rem;
      left: 1.5rem;
      z-index: 999;
      background: linear-gradient(135deg, #2AABEE, #229ED9);
      box-shadow: 0 8px 25px rgba(34, 158, 217, 0.4);
      transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
    }
    .telegram-btn:hover {
      transform: translateY(-4px) scale(1.08);
      box-shadow: 0 12px 35px rgba(34, 158, 217, 0.6);
    }
    .telegram-badge {
      animation: telegramPulse 2s infinite;
    }
    @keyframes telegramPulse {
      0%, 100% { box-shadow: 0 0 0 0 rgba(42, 171, 238, 0.6); }
      50% { box-shadow: 0 0 0 12px rgba(42, 171, 238, 0); }
    }
  </style>
  <link rel="stylesheet" href="/BIC2_Mvp/assets/hera-brand.css" />
  <script src="/BIC2_Mvp/assets/hera-language.js" defer></script>
</head>
<body class="hera-theme min-h-screen flex">

<!-- ══════════════════════════════════ SIDEBAR ══════════════════════════════════ -->
<aside class="sidebar w-64 flex-shrink-0 flex flex-col min-h-screen sticky top-0 h-screen overflow-y-auto hidden md:flex">

  <div class="p-6 border-b border-white/05">
    <div class="flex items-center gap-3">
      <img src="/BIC2_Mvp/assets/hera-mark.svg" alt="HERA" class="w-10 h-10 object-contain rounded-xl bg-white p-1 flex-shrink-0" />
      <div>
        <p class="font-bold text-white text-sm leading-tight">HERA</p>
        <p class="text-xs text-slate-400">بوابة الموارد البشرية</p>
      </div>
    </div>
  </div>

  <div class="p-6 border-b border-white/05">
    <div class="flex items-center gap-3">
      <div class="w-12 h-12 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-xl font-bold text-white flex-shrink-0">
        <?= mb_substr($user['name'], 0, 1) ?>
      </div>
      <div class="min-w-0">
        <p class="font-semibold text-white text-sm truncate"><?= htmlspecialchars($user['name']) ?></p>
        <p class="text-xs text-blue-400 font-medium truncate"><?= htmlspecialchars($catName) ?></p>
      </div>
    </div>
  </div>

  <nav class="flex-1 p-4 space-y-1">
    <a href="#attendance" class="nav-item active flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium">الحضور والاستراحة</a>
    <a href="/BIC2_Mvp/attendance.php" class="nav-item flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-slate-400">سجل الحضور</a>
    <a href="/BIC2_Mvp/profile.php" class="nav-item flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-slate-400">بروفايلي والراتب</a>
    <a href="/BIC2_Mvp/leaves.php" class="nav-item flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-slate-400">الإجازات</a>
    <a href="/BIC2_Mvp/payroll.php" class="nav-item flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-slate-400">كشوف الراتب</a>
    <a href="/BIC2_Mvp/notifications.php" class="nav-item flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-slate-400">الإشعارات</a>
  </nav>

  <div class="p-4 border-t border-white/05">
    <a href="/BIC2_Mvp/logout.php" class="flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-red-400 hover:bg-red-500/10 transition-colors">
      <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/></svg>
      تسجيل الخروج
    </a>
  </div>
</aside>

<!-- ══════════════════════════════════ MAIN ══════════════════════════════════ -->
<main class="flex-1 overflow-auto">

  <header class="sticky top-0 z-30 flex flex-col bg-slate-900/90 backdrop-blur-md border-b border-white/05">
    <div class="flex items-center justify-between px-6 py-4">
      <div>
        <h1 class="text-lg font-bold text-white">مرحباً، <?= htmlspecialchars(explode(' ', $user['name'])[0]) ?> 👋</h1>
        <p class="text-xs text-slate-400"><?= date('l، d F Y') ?></p>
      </div>

      <div class="flex items-center gap-3">
        <!-- Theme Toggle Button -->
        <button onclick="toggleTheme()" id="themeToggleBtn" class="btn-ghost rounded-xl px-3.5 py-2 text-xs font-bold text-slate-200 flex items-center gap-2 transition-all">
          <span id="themeIcon">☀️</span>
          <span id="themeText">المود الفاتح</span>
        </button>
        <a href="/BIC2_Mvp/logout.php" class="md:hidden btn-ghost rounded-xl px-3 py-1.5 text-xs text-red-400 font-semibold">خروج</a>
      </div>
    </div>

    <!-- Mobile Navigation Bar for Employee -->
    <div class="md:hidden overflow-x-auto border-t border-white/05 px-4 py-2 flex items-center gap-2 bg-slate-950/80">
      <a href="#attendance" class="px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap bg-blue-600/20 text-blue-300 border border-blue-500/30">📍 الحضور</a>
      <a href="/BIC2_Mvp/attendance.php" class="px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap bg-white/05 text-slate-300">سجل الحضور</a>
      <a href="/BIC2_Mvp/profile.php" class="px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap bg-white/05 text-slate-300">البروفايل</a>
      <a href="/BIC2_Mvp/leaves.php" class="px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap bg-white/05 text-slate-300">الإجازات</a>
      <a href="/BIC2_Mvp/payroll.php" class="px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap bg-white/05 text-slate-300">الراتب</a>
      <a href="/BIC2_Mvp/notifications.php" class="px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap bg-white/05 text-slate-300">الإشعارات</a>
    </div>
  </header>

  <div class="p-6 space-y-8 max-w-5xl mx-auto">

    <!-- ── SECTION 1: Category Info & Schedule ──────────────────── -->
    <section>
      <div class="card p-5 bg-gradient-to-r from-slate-800 to-slate-900 border-blue-500/20">
        <div class="flex flex-wrap items-center justify-between gap-4">
          <div>
            <span class="text-xs font-semibold uppercase tracking-wider text-blue-400">الفئة ومواعيد العمل</span>
            <div class="flex items-center gap-2">
              <h2 class="text-xl font-bold text-white mt-1"><?= htmlspecialchars($catName) ?></h2>
              <?php if ($workEnd < $workStart): ?>
                <span class="text-xs font-bold px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">🌙 شفت ليلي (عابر لمنتصف الليل)</span>
              <?php else: ?>
                <span class="text-xs font-bold px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30">☀️ شفت صباحي</span>
              <?php endif; ?>
            </div>
          </div>
          <div class="flex flex-wrap gap-3 text-xs">
            <div class="bg-slate-900/80 px-3 py-2 rounded-xl border border-white/10">
              <span class="text-slate-400 block">ساعات الدوام</span>
              <span class="font-mono text-emerald-400 font-bold"><?= substr($workStart, 0, 5) ?> - <?= substr($workEnd, 0, 5) ?></span>
            </div>
            <div class="bg-slate-900/80 px-3 py-2 rounded-xl border border-white/10">
              <span class="text-slate-400 block">وقت الاستراحة</span>
              <span class="font-mono text-cyan-400 font-bold"><?= substr($breakStart, 0, 5) ?> (<?= $breakDur ?> دقيقة)</span>
            </div>
            <div class="bg-slate-900/80 px-3 py-2 rounded-xl border border-white/10">
              <span class="text-slate-400 block">⏰ مهلة التسجيل</span>
              <span class="font-mono text-amber-400 font-bold"><?= $cutoffMin ?> دقيقة بعد الدوام</span>
            </div>
          </div>
        </div>
      </div>
    </section>



    <!-- ── SECTION 2: Today's Check-In & Break ──────────────────── -->
    <section id="attendance">
      <h2 class="text-sm font-semibold text-slate-400 uppercase tracking-widest mb-4">تسجيل اليوم</h2>

      <!-- Stat Cards Row -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">

        <div class="card stat-green p-4">
          <p class="text-xs text-slate-400 mb-1">وقت الدخول</p>
          <p class="text-2xl font-bold text-emerald-400" id="displayCheckIn">
            <?= $hasCheckedIn ? substr($todayRec['check_in_time'], 0, 5) : '—' ?>
          </p>
        </div>

        <div class="card stat-cyan p-4">
          <p class="text-xs text-slate-400 mb-1">الاستراحة (البريك)</p>
          <p class="text-lg font-bold text-cyan-400" id="displayBreak">
            <?php if ($hasBreakEnd): ?>
              <?= substr($todayRec['break_start_time'], 0, 5) ?> - <?= substr($todayRec['break_end_time'], 0, 5) ?>
            <?php elseif ($hasBreakStart): ?>
              مستمر ☕ (<?= substr($todayRec['break_start_time'], 0, 5) ?>)
            <?php else: ?>
              —
            <?php endif; ?>
          </p>
        </div>

        <div class="card stat-yellow p-4">
          <p class="text-xs text-slate-400 mb-1">وقت الخروج</p>
          <p class="text-2xl font-bold text-amber-400" id="displayCheckOut">
            <?= $hasCheckedOut ? substr($todayRec['check_out_time'], 0, 5) : '—' ?>
          </p>
        </div>

        <div class="card stat-blue p-4">
          <p class="text-xs text-slate-400 mb-1">الحالة</p>
          <p class="text-lg font-bold" id="displayStatus">
            <?php if (!$todayRec): ?>
              <span class="text-slate-500">لم يُسجَّل بعد</span>
            <?php elseif ($todayRec['status'] === 'present'): ?>
              <span class="text-emerald-400">✅ حاضر</span>
            <?php elseif ($todayRec['status'] === 'late'): ?>
              <span class="text-amber-400">⏰ متأخر</span>
            <?php else: ?>
              <span class="text-red-400">❌ غائب</span>
            <?php endif; ?>
          </p>
        </div>
      </div>

      <!-- GPS Check-In & Break Card -->
      <div class="card-glass p-8 flex flex-col items-center text-center">
        <div class="relative mb-6">
          <?php if (!$hasCheckedIn): ?>
            <div class="pulse-ring"></div>
          <?php endif; ?>
          <div class="w-24 h-24 rounded-full bg-slate-800 border-2 border-slate-700 flex items-center justify-center">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-12 h-12 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/>
            </svg>
          </div>
        </div>

        <h3 class="text-xl font-bold text-white mb-2" id="btnLabel">
          <?php if ($hasCheckedOut): ?>
            اكتمل تسجيل اليوم
          <?php elseif ($hasCheckedIn): ?>
            <?php if ($canCheckout): ?>
              تسجيل الانصراف متاح الآن 👋
            <?php else: ?>
              في فترة الدوام الرسمي 💻
            <?php endif; ?>
          <?php else: ?>
            تسجيل الحضور اليومي
          <?php endif; ?>
        </h3>
        <p class="text-sm text-slate-400 mb-6" id="btnSub">
          <?php if ($hasCheckedOut): ?>
            تم تسجيل حضورك وانصرافك لهذا اليوم بنجاح
          <?php elseif ($hasCheckedIn): ?>
            <?php if ($canCheckout): ?>
              انتهى وقت الدوام — انقر لتسجيل الانصراف
            <?php else: ?>
              الدوام مستمر حتى الساعة <?= substr($workEnd, 0, 5) ?> (ينشط زر الانصراف عند نهاية الشفت)
            <?php endif; ?>
          <?php else: ?>
            انقر لتحديد موقعك وتسجيل الحضور (المهلة: <?= $cutoffMin ?> دقيقة بعد بداية الدوام)
          <?php endif; ?>
        </p>

        <!-- Distance info -->
        <div id="distanceInfo" class="hidden mb-4 px-4 py-2 rounded-xl bg-blue-500/10 border border-blue-500/20 text-sm text-blue-300">
          <span id="distanceText"></span>
        </div>

        <!-- Outside warning -->
        <div id="outsideWarning" class="hidden mb-4 px-4 py-3 rounded-xl bg-red-500/15 border border-red-500/30 text-sm text-red-300 text-center max-w-xs">
          <span id="outsideText">أنت خارج نطاق الشركة</span>
        </div>

        <div id="geofenceMonitorInfo" class="hidden mb-4 px-4 py-2 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-300 text-center max-w-xs">
          يتم التحقق من بقائك داخل نطاق الشركة أثناء الدوام.
        </div>

        <!-- Main Action Buttons Grid (Always visible with smart active/dimmed states) -->
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full max-w-2xl">

          <!-- 1. BUTTON: Check-In (تسجيل الحضور) -->
          <?php if (!$hasCheckedIn): ?>
            <button
              id="checkBtn"
              onclick="handleCheckIn()"
              class="btn-checkin rounded-2xl py-3.5 px-4 text-sm font-bold text-white flex items-center justify-center gap-2"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 16l-4-4m0 0l4-4m-4 4h14"/></svg>
              تسجيل الحضور
            </button>
          <?php else: ?>
            <button disabled class="btn-done opacity-60 rounded-2xl py-3.5 px-4 text-xs font-semibold text-emerald-400 flex items-center justify-center gap-2 cursor-not-allowed">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
              تم الحضور (<?= substr($todayRec['check_in_time'], 0, 5) ?>)
            </button>
          <?php endif; ?>

          <!-- 2. BUTTON: Break (الاستراحة) -->
          <?php if (!$hasCheckedIn): ?>
            <!-- Dimmed: Check in first -->
            <button disabled class="btn-done opacity-40 rounded-2xl py-3.5 px-4 text-xs font-semibold text-slate-400 flex items-center justify-center gap-1 cursor-not-allowed" title="يجب تسجيل الدخول أولاً">
              ☕ الاستراحة
            </button>
          <?php elseif ($hasBreakEnd): ?>
            <!-- Dimmed: Break ended -->
            <button disabled class="btn-done opacity-60 rounded-2xl py-3.5 px-4 text-xs font-semibold text-cyan-400 flex items-center justify-center gap-1 cursor-not-allowed">
              ✅ تمت الاستراحة
            </button>
          <?php elseif ($hasBreakStart): ?>
            <!-- Active: Currently on break -> End Break -->
            <button onclick="handleBreak('break_out')" class="btn-break rounded-2xl py-3.5 px-4 text-xs font-bold text-white flex items-center justify-center gap-1 shadow-lg animate-pulse">
              💻 إنهاء الاستراحة
            </button>
          <?php elseif ($canStartBreak): ?>
            <!-- Active: Scheduled break time arrived -> Start Break -->
            <button onclick="handleBreak('break_in')" class="btn-break rounded-2xl py-3.5 px-4 text-xs font-bold text-white flex items-center justify-center gap-1 shadow-lg">
              ☕ بدء الاستراحة
            </button>
          <?php else: ?>
            <!-- Dimmed: Not break time yet -->
            <button disabled class="btn-done opacity-50 rounded-2xl py-3.5 px-4 text-xs font-semibold text-slate-400 flex items-center justify-center gap-1 cursor-not-allowed" title="تبدأ الاستراحة الساعة <?= substr($breakStart, 0, 5) ?>">
              ☕ الاستراحة (<?= substr($breakStart, 0, 5) ?>)
            </button>
          <?php endif; ?>

          <!-- 3. BUTTON: Check-Out (تسجيل الانصراف) -->
          <?php if ($hasCheckedOut): ?>
            <button disabled class="btn-done opacity-60 rounded-2xl py-3.5 px-4 text-xs font-semibold text-amber-400 flex items-center justify-center gap-2 cursor-not-allowed">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
              تم الانصراف (<?= substr($todayRec['check_out_time'], 0, 5) ?>)
            </button>
          <?php elseif ($canCheckout): ?>
            <!-- Active: Shift ended -> Can Checkout -->
            <button id="checkBtn" onclick="handleCheckIn()" class="btn-checkout rounded-2xl py-3.5 px-4 text-xs font-bold text-white flex items-center justify-center gap-2 shadow-lg">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7"/></svg>
              تسجيل الانصراف
            </button>
          <?php else: ?>
            <!-- Dimmed: Shift not ended yet -->
            <button disabled class="btn-done opacity-50 rounded-2xl py-3.5 px-4 text-xs font-semibold text-slate-400 flex items-center justify-center gap-1 cursor-not-allowed" title="ينشط الانصراف الساعة <?= substr($workEnd, 0, 5) ?>">
              👋 الانصراف (<?= substr($workEnd, 0, 5) ?>)
            </button>
          <?php endif; ?>

        </div>

      </div>
    </section>

    <section class="card p-5" aria-labelledby="homeNotificationsTitle">
      <div class="flex items-center justify-between gap-3 mb-4"><div><h2 id="homeNotificationsTitle" class="text-base font-bold text-white">الإشعارات</h2><p class="text-xs text-slate-400 mt-1">آخر التنبيهات والقرارات الخاصة بك</p></div><a href="/BIC2_Mvp/notifications.php" class="text-xs font-semibold text-slate-500 hover:text-slate-200">عرض الكل</a></div>
      <div id="employeeNotifications" class="space-y-2"><p class="text-sm text-slate-500">جارٍ تحميل الإشعارات...</p></div>
    </section>




  </div>
</main>

<!-- Toast -->
<div id="toast" class="card px-6 py-4 flex items-center gap-4 shadow-2xl">
  <div id="toastIcon" class="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 text-xl">✅</div>
  <div>
    <p id="toastTitle" class="font-bold text-white text-sm"></p>
    <p id="toastSub" class="text-xs text-slate-400 mt-0.5"></p>
  </div>
</div>

<!-- Telegram Chatbot Floating Icon -->
<a
  href="https://t.me/YOUR_BOT_USERNAME" 
  target="_blank" 
  id="telegramBotBtn" 
  title="مساعد تليجرام الذكي (Telegram Bot)"
  class="telegram-btn telegram-badge w-14 h-14 rounded-full flex items-center justify-center text-white cursor-pointer group"
>
  <svg class="w-7 h-7 text-white fill-current group-hover:scale-110 transition-transform" viewBox="0 0 24 24">
    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69.01-.03.01-.14-.07-.2-.08-.06-.19-.04-.27-.02-.12.02-1.96 1.25-5.54 3.69-.52.36-1 .54-1.42.53-.47-.01-1.37-.26-2.03-.48-.82-.27-1.47-.42-1.42-.88.03-.24.37-.49 1.02-.75 3.99-1.74 6.66-2.89 8.01-3.45 3.81-1.59 4.6-1.87 5.12-1.88.11 0 .37.03.54.18.14.12.18.28.2.45-.02.07-.02.14-.04.22z"/>
  </svg>
</a>

<script>
// ── Config & Telegram Bot URL ──────────────────────────────────────────────────
const TELEGRAM_BOT_URL = "https://t.me/MVP_BiC2_bot](https://t.me/MVP_BiC2_bot"; // 👈 استبدل هذا باللينك الخاص بالبوت عند إجهاده
const COMPANY_LAT    = <?= json_encode((float)$catLat) ?>;
const COMPANY_LNG    = <?= json_encode((float)$catLng) ?>;
const ALLOWED_RADIUS = <?= json_encode((int)$catRadius) ?>;
const HAS_OPEN_ATTENDANCE = <?= json_encode((bool)($hasCheckedIn && !$hasCheckedOut)) ?>;
let geofenceWatchId = null;
let geofenceIntervalId = null;
let lastLocationPingAt = 0;

async function loadEmployeeNotifications() {
  const target = document.getElementById('employeeNotifications');
  try {
    const response = await fetch('/BIC2_Mvp/api/hr.php?action=overview');
    const data = await response.json();
    if (!data.success) throw new Error(data.message || 'تعذر تحميل الإشعارات');
    const rows = (data.notifications || []).filter(n => Number(n.is_read) === 0 && !['document','letter'].includes(n.type));
    target.innerHTML = rows.length ? rows.map(n => `<article id="employee-notification-${Number(n.id)}" class="employee-notification rounded-xl border border-white/10 bg-white/5 p-3"><div class="flex items-start justify-between gap-3"><div class="min-w-0"><h3 class="text-sm font-semibold text-slate-200">${escapeNotification(n.title)}</h3><p class="mt-1 text-xs leading-5 text-slate-400">${escapeNotification(n.body)}</p><time class="mt-2 block text-[10px] text-slate-500">${escapeNotification(n.created_at)}</time></div><button type="button" onclick="markEmployeeNotificationRead(${Number(n.id)}, this)" class="shrink-0 rounded-lg p-2 text-slate-500 hover:bg-white/10 hover:text-[#1B3A3A] focus:outline-none focus:ring-2 focus:ring-[#6FA8B8]" aria-label="قراءة الإشعار" title="قراءة الإشعار"><svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M5 12.5l4.5 4.5L19 7.5"/><circle cx="12" cy="12" r="9"/></svg></button></div></article>`).join('') : '<p class="text-sm text-slate-500">لا توجد إشعارات جديدة.</p>';
  } catch (error) {
    target.innerHTML = '<p class="text-sm text-slate-500">تعذر تحميل الإشعارات الآن.</p>';
  }
}
function escapeNotification(value) { const node = document.createElement('span'); node.textContent = value ?? ''; return node.innerHTML; }
async function markEmployeeNotificationRead(notificationId, button) {
  const card = document.getElementById(`employee-notification-${notificationId}`);
  if (!card || !button || button.disabled) return;
  button.disabled = true;
  try {
    const response = await fetch('/BIC2_Mvp/api/hr.php', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'mark_notification_read', notification_id: notificationId }),
    });
    const result = await response.json();
    if (!result.success) throw new Error(result.message || 'تعذر تحديث الإشعار');
    card.remove();
    const target = document.getElementById('employeeNotifications');
    if (target && !target.querySelector('.employee-notification')) target.innerHTML = '<p class="text-sm text-slate-500">لا توجد إشعارات جديدة.</p>';
  } catch (error) {
    button.disabled = false;
    showToast('❌', 'تعذر قراءة الإشعار', error.message || 'حاول مرة أخرى.', 'bg-red-500');
  }
}

function haversineDistance(lat1, lng1, lat2, lng2) {
  const R = 6371000;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLng = (lng2 - lng1) * Math.PI / 180;
  const a = Math.sin(dLat/2)**2 + Math.cos(lat1*Math.PI/180)*Math.cos(lat2*Math.PI/180)*Math.sin(dLng/2)**2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
}

function showToast(icon, title, sub, colorClass = 'bg-emerald-500') {
  const t = document.getElementById('toast');
  document.getElementById('toastIcon').textContent = icon;
  document.getElementById('toastIcon').className   = `w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 text-xl ${colorClass}`;
  document.getElementById('toastTitle').textContent = title;
  document.getElementById('toastSub').textContent   = sub;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 4000);
}

function updateLocationUI(data) {
  const distanceInfo = document.getElementById('distanceInfo');
  const distanceText = document.getElementById('distanceText');
  const warning = document.getElementById('outsideWarning');
  const warningText = document.getElementById('outsideText');
  const monitorInfo = document.getElementById('geofenceMonitorInfo');

  if (typeof data.distance === 'number') {
    distanceInfo.classList.remove('hidden');
    distanceText.textContent = `📍 المسافة: ${data.distance} متر (المسموح: ${data.allowed_radius || ALLOWED_RADIUS} متر)`;
  }

  if (data.inside === false) {
    warning.classList.remove('hidden');
    warningText.textContent = `خارج نطاق الشركة — المسافة: ${data.distance} متر`;
    if (monitorInfo) monitorInfo.classList.add('hidden');
  } else if (data.inside === true) {
    warning.classList.add('hidden');
    if (monitorInfo) monitorInfo.classList.remove('hidden');
  }
}

function postAttendance(action, payload = {}) {
  return fetch('/BIC2_Mvp/api/attendance.php', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, ...payload }),
  }).then(r => r.json());
}

function sendLocationPing(position, force = false) {
  if (!HAS_OPEN_ATTENDANCE) return;
  const now = Date.now();
  if (!force && now - lastLocationPingAt < 30000) return;
  lastLocationPingAt = now;

  postAttendance('location_ping', {
    lat: position.coords.latitude,
    lng: position.coords.longitude,
  })
  .then(data => {
    if (!data.success || !data.tracking) return;
    updateLocationUI(data);
    if (data.event === 'left_geofence') {
      showToast('⚠️', 'تم رصد خروجك من النطاق', 'تم تسجيل الواقعة وإرسال تنبيه إلى الإدارة.', 'bg-red-500');
    } else if (data.event === 'returned_to_geofence') {
      showToast('✅', 'عدت إلى نطاق الشركة', 'تم تحديث حالة الموقع.', 'bg-emerald-500');
    }
  })
  .catch(() => {
    // Network loss must not block the portal; the next position update retries.
  });
}

function requestAndSendLocation(force = false) {
  if (!HAS_OPEN_ATTENDANCE || !navigator.geolocation) return;
  navigator.geolocation.getCurrentPosition(
    position => sendLocationPing(position, force),
    () => {},
    { enableHighAccuracy: true, timeout: 15000, maximumAge: 30000 }
  );
}

function startGeofenceMonitoring() {
  if (!HAS_OPEN_ATTENDANCE) return;
  if (!navigator.geolocation) {
    showToast('📍', 'تعذّر تشغيل مراقبة الموقع', 'يرجى تفعيل صلاحية الموقع أثناء الدوام.', 'bg-amber-500');
    return;
  }

  requestAndSendLocation(true);
  geofenceWatchId = navigator.geolocation.watchPosition(
    position => sendLocationPing(position),
    () => {},
    { enableHighAccuracy: true, timeout: 20000, maximumAge: 30000 }
  );
  geofenceIntervalId = window.setInterval(() => requestAndSendLocation(true), 60000);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) requestAndSendLocation(true);
  });
}

window.addEventListener('beforeunload', () => {
  if (geofenceWatchId !== null) navigator.geolocation.clearWatch(geofenceWatchId);
  if (geofenceIntervalId !== null) window.clearInterval(geofenceIntervalId);
});

// ── Handle Check-In / Check-Out ───────────────────────────────────────────────
function handleCheckIn() {
  if (!navigator.geolocation) {
    showToast('❌', 'الموقع الجغرافي غير مدعوم', '', 'bg-red-500');
    return;
  }

  const btn = document.getElementById('checkBtn');
  const originalHTML = btn.innerHTML;

  btn.disabled = true;
  btn.innerHTML = `<svg class="gps-spinner w-6 h-6" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/></svg> جارٍ تحديد موقعك...`;

  document.getElementById('outsideWarning').classList.add('hidden');
  document.getElementById('distanceInfo').classList.add('hidden');

  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const lat = pos.coords.latitude;
      const lng = pos.coords.longitude;
      const dist = Math.round(haversineDistance(lat, lng, COMPANY_LAT, COMPANY_LNG));

      document.getElementById('distanceInfo').classList.remove('hidden');
      document.getElementById('distanceText').textContent = `📍 المسافة: ${dist} متر (المسموح: ${ALLOWED_RADIUS} متر)`;

      if (dist > ALLOWED_RADIUS) {
        document.getElementById('outsideWarning').classList.remove('hidden');
        document.getElementById('outsideText').textContent = `أنت خارج نطاق الفئة — المسافة: ${dist} متر`;
        showToast('⚠️', 'خارج نطاق العمل', `المسافة: ${dist} متر — الحد: ${ALLOWED_RADIUS} متر`, 'bg-red-500');
        btn.disabled = false;
        btn.innerHTML = originalHTML;
        return;
      }

      postAttendance('checkin', { lat, lng })
      .then(data => {
        if (data.success) {
          showToast(data.type === 'checkin' ? '✅' : '👋', data.message, `الوقت: ${data.time}`);
          setTimeout(() => location.reload(), 1500);
        } else {
          showToast('❌', 'فشل التسجيل', data.message, 'bg-red-500');
          btn.disabled = false;
          btn.innerHTML = originalHTML;
        }
      })
      .catch(() => {
        showToast('❌', 'خطأ في الشبكة', '', 'bg-red-500');
        btn.disabled = false;
        btn.innerHTML = originalHTML;
      });
    },
    (err) => {
      showToast('📍', 'خطأ بالموقع', 'يرجى تفعيل صلاحية الوصول للموقع.', 'bg-red-500');
      btn.disabled = false;
      btn.innerHTML = originalHTML;
    },
    { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
  );
}

// ── Handle Break Actions ───────────────────────────────────────────────────────
function handleBreak(action) {
  if (!navigator.geolocation) {
    showToast('❌', 'الموقع الجغرافي غير مدعوم', 'يلزم التحقق من الموقع لبدء أو إنهاء الاستراحة.', 'bg-red-500');
    return;
  }
  navigator.geolocation.getCurrentPosition(
    (position) => {
      postAttendance(action, {
        lat: position.coords.latitude,
        lng: position.coords.longitude,
      })
      .then(data => {
        if (data.success) {
          showToast('☕', data.message, `الوقت: ${data.time}`);
          setTimeout(() => location.reload(), 1200);
        } else {
          showToast('❌', 'خطأ', data.message, 'bg-red-500');
        }
      })
      .catch(() => showToast('❌', 'خطأ في الشبكة', '', 'bg-red-500'));
    },
    () => showToast('📍', 'لم يتم تحديد الموقع', 'يرجى تفعيل الموقع ثم المحاولة مجدداً.', 'bg-red-500'),
    { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
  );
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

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  startGeofenceMonitoring();
  loadEmployeeNotifications();
});
</script>
</body>
</html>
