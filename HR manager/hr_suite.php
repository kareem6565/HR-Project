<?php
/**
 * HR Suite — unified self-service, manager and HR workspace.
 */
require_once __DIR__ . '/includes/db.php';
require_once __DIR__ . '/includes/auth.php';
require_once __DIR__ . '/includes/helpers.php';
require_once __DIR__ . '/includes/hr_platform.php';

requireLogin();
$user = getCurrentUser();
$isHr = isHRPlatformAdmin($user);
$isManager = isHRPlatformManager($user);
$canRequestLeave = ($user['role'] ?? '') !== 'admin';
$hrSuitePage = $hrSuitePage ?? ($_GET['page'] ?? 'leaves');
if (!in_array($hrSuitePage, ['leaves','payroll','notifications','reports'], true)) $hrSuitePage = 'leaves';
if ($hrSuitePage === 'reports' && !$isHr) { http_response_code(403); exit('غير مصرح لك بعرض التقارير.'); }
?>
<!doctype html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>بوابة الموارد البشرية | HERA</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Cairo:wght@400;500;600;700;800;900&display=swap" rel="stylesheet" />
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    * { font-family: Alexandria, sans-serif; }
    body { background: #07111f; color: #e2e8f0; }
    .panel { background: rgba(15, 23, 42, .86); border: 1px solid rgba(148, 163, 184, .17); border-radius: 1rem; }
    .input { width:100%; border:1px solid #334155; border-radius:.7rem; background:#0f172a; color:#f8fafc; padding:.65rem .75rem; font-size:.82rem; }
    .input:focus { outline:2px solid #6366f1; border-color:transparent; }
    .btn { border-radius:.7rem; padding:.65rem .9rem; font-size:.78rem; font-weight:700; transition:.2s; }
    .btn-primary { background:#4f46e5; color:#fff; }.btn-primary:hover{background:#6366f1}.btn-success{background:#047857;color:#fff}.btn-danger{background:#b91c1c;color:#fff}.btn-muted{background:#1e293b;color:#dbeafe}.btn-muted:hover{background:#334155}
    .badge { display:inline-flex; border-radius:999px; padding:.22rem .55rem; font-size:.68rem; font-weight:700; }
    .status-approved,.status-generated{background:#064e3b;color:#6ee7b7}.status-rejected{background:#7f1d1d;color:#fecaca}.status-pending_manager,.status-pending_hr,.status-pending{background:#78350f;color:#fde68a}.status-draft{background:#312e81;color:#c7d2fe}.status-published{background:#0c4a6e;color:#bae6fd}
    table { width:100%; border-collapse:collapse; font-size:.76rem; } th { color:#94a3b8; font-weight:600; background:#0f172a; } th,td { padding:.7rem; text-align:right; border-bottom:1px solid rgba(148,163,184,.12); vertical-align:top; }
    .toast { position:fixed; left:1rem; bottom:1rem; max-width:23rem; opacity:0; pointer-events:none; transform:translateY(1rem); transition:.2s; z-index:100; }.toast.show{opacity:1;transform:none}
    body[data-page="leaves"] [data-module]:not([data-module="leaves"]),
    body[data-page="payroll"] [data-module]:not([data-module="payroll"]),
    body[data-page="notifications"] [data-module]:not([data-module="notifications"]),
    body[data-page="reports"] [data-module]:not([data-module="reports"]) { display:none !important; }
  </style>
  <link rel="stylesheet" href="/BIC2_Mvp/assets/hera-brand.css" />
  <script src="/BIC2_Mvp/assets/hera-language.js" defer></script>
</head>
<body class="hera-theme min-h-screen" data-page="<?= htmlspecialchars($hrSuitePage, ENT_QUOTES, 'UTF-8') ?>">
  <header class="sticky top-0 z-40 border-b border-slate-700/60 bg-slate-950/90 backdrop-blur">
    <div class="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center gap-3"><img src="/BIC2_Mvp/assets/hera-mark.svg" alt="HERA" class="w-10 h-10 rounded-xl bg-white p-1 object-contain" /><div><p class="font-extrabold text-white">HERA <span class="text-indigo-300">إدارة الموارد البشرية</span></p><p class="text-xs text-slate-400 mt-1">مرحبًا <?= htmlspecialchars($user['name']) ?> — <?= htmlspecialchars($user['role']) ?></p></div></div>
      <nav class="flex flex-wrap gap-2 text-xs">
        <a class="btn btn-muted" href="/BIC2_Mvp/leaves.php">الإجازات</a>
        <a class="btn btn-muted" href="/BIC2_Mvp/payroll.php">الرواتب</a>
        <a class="btn btn-muted" href="/BIC2_Mvp/notifications.php">الإشعارات</a>
        <?php if ($isHr): ?><a class="btn btn-muted" href="/BIC2_Mvp/reports.php">التقارير</a><a class="btn btn-muted" href="/BIC2_Mvp/admin.php">لوحة الإدارة</a><?php else: ?><a class="btn btn-muted" href="/BIC2_Mvp/employee.php">الرئيسية</a><?php endif; ?>
        <a class="btn btn-danger" href="/BIC2_Mvp/logout.php">خروج</a>
      </nav>
    </div>
  </header>

  <main class="max-w-7xl mx-auto p-4 sm:p-6 space-y-6">
    <section data-module="leaves" class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div class="panel p-5"><p class="text-xs text-slate-400">رصيد الإجازات المتاح</p><p id="balanceTotal" class="text-3xl font-extrabold text-emerald-300 mt-2">—</p><p class="text-xs text-slate-400">يوم في السنة الحالية</p></div>
      <div class="panel p-5"><p class="text-xs text-slate-400">طلبات الإجازة الخاصة بي</p><p id="leaveCount" class="text-3xl font-extrabold text-amber-200 mt-2">—</p><p class="text-xs text-slate-400">منها قيد المراجعة</p></div>
      <div class="panel p-5"><p class="text-xs text-slate-400">إشعارات غير مقروءة</p><p id="unreadCount" class="text-3xl font-extrabold text-indigo-200 mt-2">—</p><p class="text-xs text-slate-400">كل القرارات والتنبيهات هنا</p></div>
    </section>

    <section id="leaves" data-module="leaves" class="panel p-5">
      <div class="flex flex-wrap justify-between gap-3 mb-5"><div><h1 class="text-lg font-extrabold text-white">الإجازات والموافقات</h1><p class="text-xs text-slate-400 mt-1">قدّم الطلب، تابع حالته، وراجع الرصيد مباشرة.</p></div></div>
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <?php if ($canRequestLeave): ?>
        <form id="leaveForm" class="bg-slate-950/50 rounded-xl p-4 space-y-3">
          <h2 class="font-bold text-sm text-white">طلب إجازة جديد</h2>
          <select id="leaveType" class="input" required></select>
          <div class="grid grid-cols-2 gap-2"><input id="leaveStart" class="input" type="date" required /><input id="leaveEnd" class="input" type="date" required /></div>
          <textarea id="leaveReason" class="input" rows="3" placeholder="سبب الطلب (اختياري)"></textarea>
          <button class="btn btn-primary w-full">إرسال الطلب</button>
        </form>
        <?php else: ?>
        <div class="bg-slate-950/50 rounded-xl p-4 border border-amber-500/20">
          <h2 class="font-bold text-sm text-amber-200">طلبات إجازة المدير غير متاحة</h2>
          <p class="text-xs text-slate-400 mt-2 leading-6">حساب مدير النظام مخصص لإدارة المنصة ولا يمكنه تقديم طلب إجازة من هذه البوابة.</p>
        </div>
        <?php endif; ?>
        <div class="lg:col-span-2 overflow-x-auto"><h2 class="font-bold text-sm text-white mb-3">أرصدتي</h2><div id="balances" class="grid grid-cols-1 sm:grid-cols-2 gap-3"></div><h2 class="font-bold text-sm text-white mt-5 mb-3">طلباتي</h2><table><thead><tr><th>النوع</th><th>الفترة</th><th>الأيام</th><th>الحالة</th><th>ملاحظات</th></tr></thead><tbody id="myLeaves"></tbody></table></div>
      </div>
    </section>

    <?php if ($isManager): ?>
    <section data-module="leaves" class="panel p-5">
      <h2 class="text-lg font-extrabold text-white">فريقي</h2>
      <p class="text-xs text-slate-400 mt-1 mb-4">عرض الموظفين المسندين إليك مباشرة.</p>
      <div id="teamMembers" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-6"></div>
      <h2 class="text-lg font-extrabold text-white">موافقات المدير / HR</h2>
      <p class="text-xs text-slate-400 mt-1 mb-4">طلبات الفريق تصل إلى المدير أولًا، ثم إلى الموارد البشرية للموافقة النهائية.</p>
      <div class="overflow-x-auto"><table><thead><tr><th>الموظف</th><th>الإجازة</th><th>الفترة</th><th>السبب</th><th>الحالة</th><th>الإجراء</th></tr></thead><tbody id="teamLeaves"></tbody></table></div>
    </section>
    <?php endif; ?>

    <?php if ($isHr): ?>
    <section data-module="leaves" class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="panel p-5"><h2 class="text-lg font-extrabold text-white">أنواع الإجازات</h2><form id="leaveTypeForm" class="grid grid-cols-2 gap-2 mt-4"><input id="ltCode" class="input" placeholder="رمز إنجليزي: annual" required /><input id="ltName" class="input" placeholder="اسم النوع" required /><input id="ltDays" class="input" type="number" min="0" step=".5" value="0" placeholder="الحد السنوي" /><label class="flex items-center gap-2 text-xs"><input id="ltPaid" type="checkbox" checked /> مدفوعة</label><label class="flex items-center gap-2 text-xs"><input id="ltManager" type="checkbox" checked /> موافقة مدير</label><button class="btn btn-primary col-span-2">حفظ نوع الإجازة</button></form><div id="leaveTypes" class="mt-4 text-xs text-slate-300 space-y-2"></div></div>
      <div class="panel p-5"><h2 class="text-lg font-extrabold text-white">تعيين مدير فريق</h2><p class="text-xs text-slate-400 mt-1">المدير يتابع فقط الموظفين المسندين إليه.</p><form id="managerForm" class="space-y-2 mt-4"><select id="managedEmployee" class="input"></select><select id="managerUser" class="input"></select><button class="btn btn-primary">حفظ المدير المباشر</button></form></div>
    </section>
    <?php endif; ?>

    <section id="payroll" data-module="payroll" class="panel p-5">
      <div class="flex flex-wrap justify-between gap-3"><div><h2 class="text-lg font-extrabold text-white">الرواتب وكشوف الدفع</h2><p class="text-xs text-slate-400 mt-1">الموظف يرى الكشوف المنشورة فقط.</p></div></div>
      <?php if ($isHr): ?>
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-5 mt-4">
        <form id="adjustmentForm" class="bg-slate-950/50 p-4 rounded-xl grid grid-cols-2 gap-2"><h3 class="col-span-2 text-sm font-bold text-white">إضافة مكوّن قبل إنشاء المسير</h3><select id="adjustmentEmployee" class="input col-span-2"></select><input id="adjustmentMonth" class="input" type="month" required /><select id="adjustmentType" class="input"><option value="allowance">بدل</option><option value="bonus">مكافأة</option><option value="commission">عمولة</option><option value="overtime">وقت إضافي</option><option value="deduction">خصم يدوي</option></select><input id="adjustmentAmount" class="input" type="number" min=".01" step=".01" placeholder="القيمة" required /><input id="adjustmentDescription" class="input" placeholder="الوصف" required /><button class="btn btn-primary col-span-2">إضافة المكوّن</button></form>
        <form id="runForm" class="bg-slate-950/50 p-4 rounded-xl space-y-3"><h3 class="text-sm font-bold text-white">إنشاء مسير رواتب</h3><input id="runMonth" class="input" type="month" required /><button class="btn btn-success w-full">إنشاء مسودة المسير</button><p class="text-xs text-slate-400">أضف البدلات والمكافآت أولًا، ثم أنشئ المسير وانشره بعد المراجعة.</p></form>
      </div>
      <div class="mt-5 overflow-x-auto"><h3 class="text-sm font-bold text-white mb-3">مسيرات الرواتب</h3><table><thead><tr><th>الفترة</th><th>الموظفون</th><th>الإجمالي</th><th>الحالة</th><th>إجراء</th></tr></thead><tbody id="payrollRuns"></tbody></table></div>
      <?php endif; ?>
      <div class="mt-5"><h3 class="text-sm font-bold text-white mb-3">كشوف راتبي المنشورة</h3><div id="payslips" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3"></div></div>
    </section>


    <?php if ($isHr): ?>
    <section id="reports" data-module="reports" class="panel p-5"><h2 class="text-lg font-extrabold text-white">التقارير والتصدير</h2><p class="text-xs text-slate-400 mt-1">Excel يُنزَّل مباشرة، والنسخة القابلة للطباعة تسمح بحفظها PDF من المتصفح.</p><div class="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-4"><input id="reportFrom" class="input" type="date" /><input id="reportTo" class="input" type="date" /><input id="reportMonth" class="input" type="month" /></div><div class="flex flex-wrap gap-2 mt-3"><button class="btn btn-muted" onclick="exportReport('attendance','xls')">Excel الحضور</button><button class="btn btn-muted" onclick="exportReport('leaves','xls')">Excel الإجازات</button><button class="btn btn-muted" onclick="exportReport('payroll','xls')">Excel الرواتب</button><button class="btn btn-primary" onclick="exportReport('attendance','print')">PDF / طباعة الحضور</button><button class="btn btn-primary" onclick="exportReport('leaves','print')">PDF / طباعة الإجازات</button><button class="btn btn-primary" onclick="exportReport('payroll','print')">PDF / طباعة الرواتب</button></div></section>
    <?php endif; ?>

    <section id="notifications" data-module="notifications" class="panel p-5"><div class="flex justify-between items-center"><div><h2 class="text-lg font-extrabold text-white">الإشعارات</h2><p class="text-xs text-slate-400 mt-1">تنبيهات الطلبات والقرارات وكشوف الرواتب.</p></div><button class="btn btn-muted" onclick="markNotificationsRead()">قراءة الكل</button></div><div id="notificationsList" class="mt-4 space-y-2"></div></section>
  </main>
  <div id="toast" class="toast panel p-4 text-sm"></div>

<script>
const API = '/BIC2_Mvp/api/hr.php';
const IS_HR = <?= $isHr ? 'true' : 'false' ?>;
const IS_MANAGER = <?= $isManager ? 'true' : 'false' ?>;
const SUITE_PAGE = <?= json_encode($hrSuitePage) ?>;
let overview = null;

function esc(value) { const d=document.createElement('div'); d.textContent=value ?? ''; return d.innerHTML; }
function status(value) { return `<span class="badge status-${esc(value)}">${esc(({pending_manager:'بانتظار المدير',pending_hr:'بانتظار HR',approved:'معتمد',rejected:'مرفوض',cancelled:'ملغي',pending:'قيد المراجعة',generated:'تم الإصدار',draft:'مسودة',published:'منشور'})[value] || value)}</span>`; }
function toast(message, bad=false) { const t=document.getElementById('toast'); t.textContent=message; t.classList.toggle('border-red-500/60',bad); t.classList.add('show'); setTimeout(()=>t.classList.remove('show'),4200); }
async function get(action, params={}) { const q=new URLSearchParams({action,...params}); const r=await fetch(`${API}?${q}`); const data=await r.json(); if(!data.success) throw new Error(data.message); return data; }
async function post(action, payload={}) { const r=await fetch(API,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,...payload})}); const data=await r.json(); if(!data.success) throw new Error(data.message); return data; }
function period(input) { const [year,month]=input.split('-').map(Number); return {year,month}; }
function dateValue(offset=0) { const d=new Date(); d.setDate(d.getDate()+offset); return d.toISOString().slice(0,10); }

function renderOverview(data) {
  overview=data;
  const balances=data.balances || []; const requests=data.my_leaves || [];
  const balanceTotal=document.getElementById('balanceTotal'); if(balanceTotal) balanceTotal.textContent = balances.reduce((sum,b)=>sum+Number(b.remaining_days),0).toFixed(1);
  const leaveCount=document.getElementById('leaveCount'); if(leaveCount) leaveCount.textContent = requests.filter(r=>r.status.startsWith('pending')).length;
  const unreadCount=document.getElementById('unreadCount'); if(unreadCount) unreadCount.textContent = data.unread_notifications;
  const leaveType=document.getElementById('leaveType');
  if(leaveType) leaveType.innerHTML = balances.length ? balances.map(b=>`<option value="${b.leave_type_id}">${esc(b.name)} — المتاح ${Number(b.remaining_days).toFixed(1)} يوم</option>`).join('') : '<option>لا توجد أنواع إجازات متاحة</option>';
  const balancesNode=document.getElementById('balances'); if(balancesNode) balancesNode.innerHTML = balances.map(b=>`<div class="bg-slate-950/50 rounded-xl p-3 border border-slate-700/50"><div class="flex justify-between gap-2"><b class="text-sm text-white">${esc(b.name)}</b><span class="text-emerald-300">${Number(b.remaining_days).toFixed(1)} يوم</span></div><p class="text-xs text-slate-400 mt-1">المستحق ${b.entitled_days} — المستخدم ${b.used_days}</p></div>`).join('') || '<p class="text-xs text-slate-400">لا توجد أرصدة بعد.</p>';
  const myLeavesNode=document.getElementById('myLeaves'); if(myLeavesNode) myLeavesNode.innerHTML = requests.map(r=>`<tr><td>${esc(r.leave_type_name)}</td><td>${r.start_date} → ${r.end_date}</td><td>${r.days_count}</td><td>${status(r.status)}</td><td>${esc(r.hr_comment || r.manager_comment || '—')}</td></tr>`).join('') || '<tr><td colspan="5" class="text-slate-400">لا توجد طلبات حتى الآن.</td></tr>';
  renderTeamLeaves(data.team_leaves || []);
  renderNotifications(data.notifications || []);
}
function renderTeamLeaves(rows) {
  const node=document.getElementById('teamLeaves'); if(!node) return;
  node.innerHTML=rows.map(r=>`<tr><td>${esc(r.employee_name)}<br><span class="text-slate-500">${esc(r.emp_code)}</span></td><td>${esc(r.leave_type_name)}</td><td>${r.start_date} → ${r.end_date}<br>${r.days_count} يوم</td><td>${esc(r.reason || '—')}</td><td>${status(r.status)}</td><td>${r.status==='pending_manager' || (IS_HR && r.status==='pending_hr') ? `<div class="flex gap-1"><button class="btn btn-success" onclick="decideLeave(${r.id},'approved')">موافقة</button><button class="btn btn-danger" onclick="decideLeave(${r.id},'rejected')">رفض</button></div>` : '—'}</td></tr>`).join('') || '<tr><td colspan="6" class="text-slate-400">لا توجد طلبات تحتاج إجراء.</td></tr>';
}
async function loadTeamMembers(){if(!IS_MANAGER)return;try{const data=await get('team_members');const node=document.getElementById('teamMembers');if(!node)return;node.innerHTML=data.members.map(m=>`<div class="bg-slate-950/45 rounded-xl p-3 border border-slate-700/50"><b class="text-sm text-white">${esc(m.name)}</b><p class="text-xs text-slate-400 mt-1">${esc(m.emp_code)} · ${esc(m.category_name||'عام')}</p>${m.manager_name?`<p class="text-[10px] text-indigo-300 mt-1">المدير: ${esc(m.manager_name)}</p>`:''}</div>`).join('')||'<p class="text-sm text-slate-400">لا يوجد موظفون مسندون للفريق.</p>'}catch(e){toast(e.message,true)}}
function renderNotifications(rows) { const node=document.getElementById('notificationsList'); if(!node)return; const visible=rows.filter(n=>!['document','letter'].includes(n.type)); node.innerHTML=visible.map(n=>`<div class="flex justify-between gap-3 rounded-xl bg-slate-950/45 p-3 border ${n.is_read==0?'border-indigo-500/40':'border-slate-700/50'}"><div><b class="text-xs text-white">${esc(n.title)}</b><p class="text-xs text-slate-400 mt-1">${esc(n.body)}</p></div><span class="text-[10px] text-slate-500 whitespace-nowrap">${esc(n.created_at)}</span></div>`).join('') || '<p class="text-sm text-slate-400">لا توجد إشعارات.</p>'; }
async function loadOverview(){ try{renderOverview(await get('overview'));}catch(e){toast(e.message,true)} }
async function decideLeave(id, decision){ const comment=prompt(decision==='approved'?'ملاحظة اختيارية للموافقة:':'سبب الرفض:') ?? ''; try{await post('leave_decision',{request_id:id,decision,comment});toast('تم حفظ القرار.');refreshAll()}catch(e){toast(e.message,true)} }
async function loadPayroll(){ try{const pays=await get('my_payslips'); const slipsNode=document.getElementById('payslips'); if(slipsNode) slipsNode.innerHTML=pays.payslips.map(p=>`<div class="bg-slate-950/50 p-4 rounded-xl border border-slate-700/50"><div class="flex justify-between"><b>راتب ${p.period_month}/${p.period_year}</b>${status(p.status)}</div><p class="text-2xl text-emerald-300 font-extrabold mt-3">${Number(p.net_salary).toLocaleString('ar')} ر.س</p><p class="text-xs text-slate-400 mt-2">أساسي ${p.basic_salary} · بدلات ${p.allowances} · مكافآت ${p.bonuses} · خصومات ${(Number(p.absence_deductions)+Number(p.late_deductions)+Number(p.other_deductions)).toFixed(2)}</p></div>`).join('') || '<p class="text-sm text-slate-400">لا توجد كشوف منشورة حتى الآن.</p>'; if(IS_HR && document.getElementById('payrollRuns')) renderRuns((await get('payroll_runs')).runs);}catch(e){toast(e.message,true)} }
function renderRuns(runs){const node=document.getElementById('payrollRuns');if(!node)return;node.innerHTML=runs.map(r=>`<tr><td>${r.period_month}/${r.period_year}</td><td>${r.employee_count}</td><td>${Number(r.total_net).toLocaleString('ar')} ر.س</td><td>${status(r.status)}</td><td>${r.status==='draft'?`<button class="btn btn-success" onclick="publishRun(${r.id})">نشر</button>`:'—'}</td></tr>`).join('')||'<tr><td colspan="5" class="text-slate-400">لا توجد مسيرات.</td></tr>'}
async function publishRun(id){if(!confirm('هل تريد نشر المسير؟ سيصبح ظاهرًا للموظفين.'))return;try{await post('publish_payroll_run',{run_id:id});toast('تم نشر المسير.');loadPayroll()}catch(e){toast(e.message,true)}}
async function loadHrSetup(){if(!IS_HR)return;try{const [types,staff]=await Promise.all([get('leave_types'),get('employees')]);document.getElementById('leaveTypes').innerHTML=types.leave_types.map(t=>`<div class="flex justify-between bg-slate-950/40 p-2 rounded-lg"><span>${esc(t.name)} <span class="text-slate-500">(${esc(t.code)})</span></span><span>${t.default_days} يوم · ${t.is_paid==1?'مدفوعة':'بدون راتب'}</span></div>`).join('');const employees=staff.employees.filter(e=>e.role!=='manager');const managers=staff.employees.filter(e=>e.role==='manager');const option=(e)=>`<option value="${e.id}">${esc(e.name)} (${esc(e.emp_code)})</option>`;document.getElementById('managedEmployee').innerHTML=employees.map(option).join('')||'<option>لا يوجد موظفون</option>';document.getElementById('managerUser').innerHTML='<option value="">بدون مدير</option>'+managers.map(option).join('');document.getElementById('adjustmentEmployee').innerHTML=staff.employees.map(option).join('');}catch(e){toast(e.message,true)}}
async function markNotificationsRead(){try{await post('mark_notification_read');toast('تم تعليم الإشعارات كمقروءة.');loadOverview()}catch(e){toast(e.message,true)}}
function exportReport(type,format){const from=document.getElementById('reportFrom').value, to=document.getElementById('reportTo').value, month=document.getElementById('reportMonth').value;let params={action:'report',type,format,from,to};if(month){const p=period(month);params.year=p.year;params.month=p.month}window.open(`${API}?${new URLSearchParams(params)}`,'_blank');}
async function refreshAll(){
  if (SUITE_PAGE === 'leaves') await Promise.all([loadOverview(),loadHrSetup(),loadTeamMembers()]);
  else if (SUITE_PAGE === 'payroll') await loadPayroll();
  else if (SUITE_PAGE === 'notifications') await loadOverview();
}

const leaveForm=document.getElementById('leaveForm');
if(leaveForm) leaveForm.addEventListener('submit',async e=>{e.preventDefault();try{await post('submit_leave',{leave_type_id:document.getElementById('leaveType').value,start_date:document.getElementById('leaveStart').value,end_date:document.getElementById('leaveEnd').value,reason:document.getElementById('leaveReason').value});toast('تم إرسال الطلب.');e.target.reset();refreshAll()}catch(err){toast(err.message,true)}});
if(IS_HR && SUITE_PAGE === 'leaves' && document.getElementById('leaveTypeForm')){document.getElementById('leaveTypeForm').addEventListener('submit',async e=>{e.preventDefault();try{await post('save_leave_type',{code:ltCode.value,name:ltName.value,default_days:ltDays.value,is_paid:ltPaid.checked,requires_manager_approval:ltManager.checked,is_active:true});toast('تم حفظ نوع الإجازة.');e.target.reset();loadHrSetup();loadOverview()}catch(err){toast(err.message,true)}});document.getElementById('managerForm').addEventListener('submit',async e=>{e.preventDefault();try{await post('assign_manager',{employee_id:managedEmployee.value,manager_id:managerUser.value});toast('تم تحديث المدير.');loadHrSetup()}catch(err){toast(err.message,true)}});document.getElementById('adjustmentForm').addEventListener('submit',async e=>{e.preventDefault();try{const p=period(adjustmentMonth.value);await post('add_adjustment',{user_id:adjustmentEmployee.value,year:p.year,month:p.month,component_type:adjustmentType.value,amount:adjustmentAmount.value,description:adjustmentDescription.value});toast('تمت إضافة المكوّن.');e.target.reset()}catch(err){toast(err.message,true)}});document.getElementById('runForm').addEventListener('submit',async e=>{e.preventDefault();try{const p=period(runMonth.value);await post('create_payroll_run',p);toast('تم إنشاء مسودة المسير.');loadPayroll()}catch(err){toast(err.message,true)}})}
const currentMonth=new Date().toISOString().slice(0,7);const leaveStart=document.getElementById('leaveStart'),leaveEnd=document.getElementById('leaveEnd');if(leaveStart){leaveStart.value=dateValue(1);leaveEnd.value=dateValue(1);}if(IS_HR){const am=document.getElementById('adjustmentMonth'),rm=document.getElementById('runMonth'),rf=document.getElementById('reportFrom'),rt=document.getElementById('reportTo'),rmo=document.getElementById('reportMonth');if(am)am.value=currentMonth;if(rm)rm.value=currentMonth;if(rf)rf.value=new Date(new Date().getFullYear(),new Date().getMonth(),1).toISOString().slice(0,10);if(rt)rt.value=dateValue();if(rmo)rmo.value=currentMonth;}refreshAll();
</script>
</body>
</html>
