<?php
/**
 * profile.php — Comprehensive Employee Profile & Performance Report Page
 */
require_once __DIR__ . '/includes/db.php';
require_once __DIR__ . '/includes/auth.php';
require_once __DIR__ . '/includes/helpers.php';

requireLogin();

$currentUser = getCurrentUser();
$targetUserId = isset($_GET['id']) ? (int)$_GET['id'] : (int)$currentUser['id'];

// If logged in user is employee, prevent viewing other profiles
if ($currentUser['role'] === 'employee' && $targetUserId !== (int)$currentUser['id']) {
    redirect('/BIC2_Mvp/employee.php');
}
?>
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>الملف الشخصي والتقرير التفصيلي — نظام الحضور والرواتب</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Cairo:wght@400;500;600;700;800;900&display=swap" rel="stylesheet" />
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    * { font-family: 'Cairo', sans-serif; }
    body { background: #080c14; color: #f8fafc; }

    .card { background: rgba(30,41,59,0.85); border: 1px solid rgba(255,255,255,0.07); border-radius: 1rem; }
    .card-glass { background: rgba(255,255,255,0.04); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.08); border-radius: 1rem; }

    .stat-card { border-top: 3px solid; transition: transform .2s, box-shadow .2s; }
    .stat-card:hover { transform: translateY(-3px); box-shadow: 0 8px 24px rgba(0,0,0,.4); }
    .stat-blue   { border-color: #3b82f6; }
    .stat-green  { border-color: #10b981; }
    .stat-yellow { border-color: #f59e0b; }
    .stat-red    { border-color: #ef4444; }
    .stat-purple { border-color: #a855f7; }

    .badge-present { background: rgba(16,185,129,0.15); color: #34d399; border: 1px solid rgba(16,185,129,0.3); }
    .badge-late    { background: rgba(245,158,11,0.15);  color: #fbbf24; border: 1px solid rgba(245,158,11,0.3); }
    .badge-absent  { background: rgba(239,68,68,0.15);   color: #f87171; border: 1px solid rgba(239,68,68,0.3); }
    .badge-admin   { background: rgba(139,92,246,0.15);  color: #c4b5fd; border: 1px solid rgba(139,92,246,0.3); }
    .badge-hr      { background: rgba(236,72,153,0.15);  color: #f472b6; border: 1px solid rgba(236,72,153,0.3); }
    .badge-emp     { background: rgba(59,130,246,0.15);  color: #93c5fd; border: 1px solid rgba(59,130,246,0.3); }

    .btn-ghost { background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1); transition: all 0.25s; }
    .btn-ghost:hover { background: rgba(255,255,255,0.1); }

    table { border-collapse: separate; border-spacing: 0; }
    thead th { background: rgba(15,23,42,0.8); }
    tbody tr { transition: background 0.15s; }
    tbody tr:hover { background: rgba(255,255,255,0.03); }

    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: #0f172a; }
    ::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
  </style>
  <link rel="stylesheet" href="/BIC2_Mvp/assets/hera-brand.css" />
  <script src="/BIC2_Mvp/assets/hera-language.js" defer></script>
</head>
<body class="hera-theme hera-has-extra-sidebar hera-profile-layout min-h-screen p-4 md:p-8">

  <aside class="hera-extra-sidebar" aria-label="HERA navigation">
    <a class="hera-extra-brand" href="/BIC2_Mvp/employee.php"><img src="/BIC2_Mvp/assets/hera-mark.svg" alt="HERA" /><span><strong>HERA</strong><small>بوابة الموارد البشرية</small></span></a>
    <nav>
      <a href="/BIC2_Mvp/employee.php">الرئيسية</a>
      <a href="/BIC2_Mvp/attendance.php">سجل الحضور</a>
      <a class="active" href="/BIC2_Mvp/profile.php">بروفايلي التفصيلي والراتب</a>
      <a href="/BIC2_Mvp/leaves.php">الإجازات</a><a href="/BIC2_Mvp/payroll.php">الراتب</a><a href="/BIC2_Mvp/notifications.php">الإشعارات</a>
    </nav>
    <a class="hera-extra-logout" href="/BIC2_Mvp/logout.php">تسجيل الخروج</a>
  </aside>

  <div class="max-w-6xl mx-auto space-y-6">

    <!-- Top Bar Navigation -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <a href="<?= $currentUser['role'] === 'hr' ? '/BIC2_Mvp/workspace.php' : ($currentUser['role'] === 'admin' ? '/BIC2_Mvp/admin.php' : '/BIC2_Mvp/employee.php') ?>" class="btn-ghost rounded-xl px-4 py-2 text-sm text-slate-300 flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/></svg>
          العودة للوحة الرئيسية
        </a>
        <h1 class="text-xl font-bold text-white">التقرير الشامل والملف الشخصي</h1>
      </div>
      <button onclick="window.print()" class="btn-ghost rounded-xl px-4 py-2 text-sm text-slate-300 flex items-center gap-2">
        <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"/></svg>
        طباعة التقرير
      </button>
    </div>

    <!-- ── Profile Header Card ────────────────────────────────────── -->
    <div class="card p-6 bg-gradient-to-r from-slate-800 via-slate-900 to-slate-800">
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-6" id="profileHeader">
        <div class="flex items-center gap-4">
          <div class="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-3xl font-black text-white" id="userAvatar">
            —
          </div>
          <div>
            <div class="flex items-center gap-3">
              <h2 class="text-2xl font-bold text-white" id="userName">جارٍ التحميل...</h2>
              <span id="userRoleBadge" class="text-xs px-3 py-1 rounded-full font-semibold"></span>
            </div>
            <p class="text-sm text-slate-400 mt-1">كود الموظف: <span class="font-mono text-blue-400" id="userCode">—</span> | الفئة: <span class="text-teal-400 font-semibold" id="userCategory">—</span></p>
          </div>
        </div>

        <div class="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
          <div class="bg-slate-900/80 px-4 py-3 rounded-xl border border-white/10">
            <span class="text-slate-400 block mb-0.5">تاريخ الانضمام</span>
            <span class="font-semibold text-white" id="userJoinDate">—</span>
          </div>
          <div class="bg-slate-900/80 px-4 py-3 rounded-xl border border-white/10">
            <span class="text-slate-400 block mb-0.5">ساعات الدوام</span>
            <span class="font-mono text-emerald-400 font-semibold" id="userShift">—</span>
          </div>
          <div class="bg-slate-900/80 px-4 py-3 rounded-xl border border-white/10">
            <span class="text-slate-400 block mb-0.5">الإجازة السنوية</span>
            <span class="font-semibold text-blue-400" id="userVacation">—</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Overview Stat Cards ────────────────────────────────────── -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="card stat-card stat-blue p-5">
        <p class="text-xs text-slate-400 font-medium mb-1">أيام الحضور اليومي</p>
        <p class="text-3xl font-black text-emerald-400" id="statPresentDays">0</p>
        <p class="text-xs text-slate-500 mt-1">تسجيل حضور في الموعد</p>
      </div>

      <div class="card stat-card stat-yellow p-5">
        <p class="text-xs text-slate-400 font-medium mb-1">عدد مرات التأخير</p>
        <p class="text-3xl font-black text-amber-400" id="statLateDays">0</p>
        <p class="text-xs text-amber-500/80 mt-1">تأخير عن موعد الشفت</p>
      </div>

      <div class="card stat-card stat-red p-5">
        <p class="text-xs text-slate-400 font-medium mb-1">أيام الغياب</p>
        <p class="text-3xl font-black text-red-400" id="statAbsentDays">0</p>
        <p class="text-xs text-red-500/80 mt-1">لم يتم تسجيل حضور</p>
      </div>

      <div class="card stat-card stat-purple p-5">
        <p class="text-xs text-slate-400 font-medium mb-1">صافي الراتب التقديري</p>
        <p class="text-2xl font-black text-purple-400" id="statNetSalary">0 ر.س</p>
        <p class="text-xs text-slate-500 mt-1">بعد الخصومات المستحقة</p>
      </div>
    </div>

    <!-- ── Financial & Payroll Breakdown Card ─────────────────────── -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">

      <!-- Payroll Card -->
      <div class="card p-6 md:col-span-2 space-y-4">
        <div class="flex items-center justify-between border-b border-white/10 pb-3">
          <h3 class="font-bold text-white text-lg flex items-center gap-2">
            💳 تفاصيل الراتب والخصومات المالية
          </h3>
          <span class="text-xs text-slate-400">حساب تلقائي حسب الحضور والغياب</span>
        </div>

        <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div class="bg-white/05 p-3 rounded-xl border border-white/05">
            <p class="text-xs text-slate-400 mb-1">الراتب الأساسي</p>
            <p class="text-lg font-bold text-emerald-400" id="pBasicSalary">0 ر.س</p>
          </div>
          <div class="bg-white/05 p-3 rounded-xl border border-white/05">
            <p class="text-xs text-slate-400 mb-1">أجر اليوم (اليومية)</p>
            <p class="text-lg font-bold text-blue-400" id="pDailyRate">0 ر.س</p>
          </div>
          <div class="bg-white/05 p-3 rounded-xl border border-white/05">
            <p class="text-xs text-slate-400 mb-1">خصم الغياب</p>
            <p class="text-lg font-bold text-red-400" id="pAbsenceDeduction">0 ر.س</p>
          </div>
          <div class="bg-white/05 p-3 rounded-xl border border-white/05">
            <p class="text-xs text-slate-400 mb-1">خصم التأخير</p>
            <p class="text-lg font-bold text-amber-400" id="pLateDeduction">0 ر.س</p>
          </div>
        </div>

        <div class="p-4 rounded-xl bg-purple-500/10 border border-purple-500/20 flex flex-wrap items-center justify-between gap-4">
          <div>
            <p class="text-xs text-purple-300">إجمالي الخصومات المستحقة: <span class="font-bold text-red-400" id="pTotalDeductions">0 ر.س</span></p>
            <p class="text-xs text-slate-400 mt-0.5">خصم يوم كامل عن كل يوم غياب + ربع يوم عن كل تأخير</p>
          </div>
          <div class="text-right">
            <span class="text-xs text-slate-400 block">الراتب الصافي المستحق:</span>
            <span class="text-2xl font-black text-emerald-400" id="pNetSalary">0 ر.س</span>
          </div>
        </div>
      </div>

      <!-- Shift & Break Rules Card -->
      <div class="card p-6 space-y-4">
        <div class="border-b border-white/10 pb-3">
          <h3 class="font-bold text-white text-base">⏰ قوانين الشفت والمهلة</h3>
        </div>
        <div class="space-y-3 text-xs">
          <div class="flex justify-between py-1 border-b border-white/05">
            <span class="text-slate-400">بداية ونهاية الدوام</span>
            <span class="font-mono text-emerald-400 font-semibold" id="ruleShift">—</span>
          </div>
          <div class="flex justify-between py-1 border-b border-white/05">
            <span class="text-slate-400">مواعيد الاستراحة (البريك)</span>
            <span class="font-mono text-cyan-400 font-semibold" id="ruleBreak">—</span>
          </div>
          <div class="flex justify-between py-1 border-b border-white/05">
            <span class="text-slate-400">مدة البريك المسموحة</span>
            <span class="text-slate-200" id="ruleBreakDur">—</span>
          </div>
          <div class="flex justify-between py-1">
            <span class="text-slate-400">مهلة إغلاق تسجيل الدخول</span>
            <span class="font-semibold text-amber-400" id="ruleCutoff">—</span>
          </div>
        </div>
      </div>

    </div>

    <!-- ── Full Attendance & GPS Movement History Table ────────────── -->
    <div class="card overflow-hidden">
      <div class="flex items-center justify-between px-6 py-4 border-b border-white/05">
        <h3 class="font-bold text-white flex items-center gap-2">
          📍 سجل الحضور الجغرافي والتأخير والتنقلات الكامل
        </h3>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-xs text-slate-400 border-b border-white/05">
              <th class="px-5 py-3 text-right font-medium">التاريخ</th>
              <th class="px-5 py-3 text-right font-medium">وقت الدخول</th>
              <th class="px-5 py-3 text-right font-medium">الاستراحة (البريك)</th>
              <th class="px-5 py-3 text-right font-medium">وقت الخروج</th>
              <th class="px-5 py-3 text-right font-medium">المسافة عن المقر</th>
              <th class="px-5 py-3 text-right font-medium">الحالة</th>
              <th class="px-5 py-3 text-right font-medium">خريطة الموقع</th>
            </tr>
          </thead>
          <tbody id="profileLogsBody" class="divide-y divide-white/04 text-slate-300">
            <tr><td colspan="7" class="text-center py-8 text-slate-500">جارٍ تحميل بيانات التقرير...</td></tr>
          </tbody>
        </table>
      </div>
    </div>

  </div>

<script>
const TARGET_ID = <?= json_encode($targetUserId) ?>;

function loadProfile() {
  fetch('/BIC2_Mvp/api/profile.php?user_id=' + TARGET_ID)
    .then(r => r.json())
    .then(data => {
      if (!data.success) {
        alert(data.message);
        return;
      }

      const u = data.user;
      const s = data.stats;
      const p = data.payroll;
      const logs = data.logs;

      // User Header
      document.getElementById('userAvatar').textContent = u.name.substring(0, 1);
      document.getElementById('userName').textContent = u.name;
      document.getElementById('userCode').textContent = u.emp_code;
      document.getElementById('userCategory').textContent = u.category_name;
      document.getElementById('userJoinDate').textContent = u.created_at.substring(0, 10);
      document.getElementById('userShift').textContent = u.work_start_time.substring(0, 5) + ' - ' + u.work_end_time.substring(0, 5);
      document.getElementById('userVacation').textContent = u.yearly_vacation_days + ' يوم';

      // Role badge
      const roleBadge = document.getElementById('userRoleBadge');
      if (u.role === 'admin') {
        roleBadge.className = 'text-xs px-3 py-1 rounded-full font-semibold badge-admin';
        roleBadge.textContent = 'مدير النظام';
      } else if (u.role === 'hr') {
        roleBadge.className = 'text-xs px-3 py-1 rounded-full font-semibold badge-hr';
        roleBadge.textContent = 'مسؤول موارد بشرية (HR)';
      } else {
        roleBadge.className = 'text-xs px-3 py-1 rounded-full font-semibold badge-emp';
        roleBadge.textContent = 'موظف';
      }

      // Stats
      document.getElementById('statPresentDays').textContent = s.present_days;
      document.getElementById('statLateDays').textContent    = s.late_days;
      document.getElementById('statAbsentDays').textContent  = s.absent_days;
      document.getElementById('statNetSalary').textContent   = p.net_salary.toLocaleString('ar') + ' ر.س';

      // Payroll
      document.getElementById('pBasicSalary').textContent      = p.basic_salary.toLocaleString('ar') + ' ر.س';
      document.getElementById('pDailyRate').textContent        = p.daily_rate.toLocaleString('ar') + ' ر.س';
      document.getElementById('pAbsenceDeduction').textContent = p.absence_deduction.toLocaleString('ar') + ' ر.س';
      document.getElementById('pLateDeduction').textContent    = p.late_deduction.toLocaleString('ar') + ' ر.س';
      document.getElementById('pTotalDeductions').textContent  = p.total_deductions.toLocaleString('ar') + ' ر.س';
      document.getElementById('pNetSalary').textContent        = p.net_salary.toLocaleString('ar') + ' ر.س';

      // Rules
      document.getElementById('ruleShift').textContent    = u.work_start_time.substring(0, 5) + ' - ' + u.work_end_time.substring(0, 5);
      document.getElementById('ruleBreak').textContent    = u.break_start_time.substring(0, 5);
      document.getElementById('ruleBreakDur').textContent = u.break_duration + ' دقيقة';
      document.getElementById('ruleCutoff').textContent   = u.cutoff_minutes + ' دقيقة بعد الدوام';

      // Logs Table
      const tbody = document.getElementById('profileLogsBody');
      if (!logs.length) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center py-8 text-slate-500">لا توجد سجلات حضور مسجلة لـ هذا الموظف.</td></tr>`;
        return;
      }

      const statusMap = {
        present: ['badge-present', 'حاضر'],
        late:    ['badge-late', 'متأخر'],
        absent:  ['badge-absent', 'غائب'],
      };

      tbody.innerHTML = logs.map(r => {
        const [cls, label] = statusMap[r.status] || ['text-slate-400', r.status];
        const mapLink = (r.lat_in && r.lng_in)
          ? `<a href="https://www.google.com/maps?q=${r.lat_in},${r.lng_in}" target="_blank" class="text-blue-400 hover:text-blue-300 text-xs underline font-medium">📍 الخريطة</a>`
          : '—';
        const breakStr = r.break_start_time
          ? `<span class="text-xs font-mono text-cyan-400">${r.break_start_time.substring(0,5)} - ${r.break_end_time ? r.break_end_time.substring(0,5) : 'مستمر'}</span>`
          : '—';

        return `
          <tr>
            <td class="px-5 py-3 text-white font-medium">${r.date}</td>
            <td class="px-5 py-3 font-mono text-emerald-400">${r.check_in_time ? r.check_in_time.substring(0,5) : '—'}</td>
            <td class="px-5 py-3 font-mono">${breakStr}</td>
            <td class="px-5 py-3 font-mono text-amber-400">${r.check_out_time ? r.check_out_time.substring(0,5) : '—'}</td>
            <td class="px-5 py-3 text-slate-400">${r.distance_in_meters !== null ? r.distance_in_meters + ' م' : '—'}</td>
            <td class="px-5 py-3"><span class="text-xs font-medium px-2.5 py-1 rounded-full ${cls}">${label}</span></td>
            <td class="px-5 py-3">${mapLink}</td>
          </tr>
        `;
      }).join('');
    });
}

loadProfile();
</script>
</body>
</html>
