<?php
$heraShellUser = getCurrentUser();
$heraShellRole = (string)($heraShellUser['role'] ?? 'employee');
$heraShellName = trim((string)($heraShellUser['name'] ?? 'HERA'));
$heraShellPath = basename((string)($_SERVER['SCRIPT_NAME'] ?? ''));
$heraShellSection = (string)($hrSuitePage ?? '');
$heraShellActive = $heraShellSection !== '' ? $heraShellSection : match ($heraShellPath) {
    'admin.php' => 'admin',
    'employee.php' => 'employee',
    'attendance.php' => 'attendance',
    'profile.php' => 'profile',
    default => '',
};
$heraShellManagementLinks = [
    ['key' => 'admin', 'label' => 'لوحة الموارد البشرية', 'href' => '/BIC2_Mvp/admin.php'],
    ['key' => 'attendance', 'label' => 'سجل الحضور', 'href' => $heraShellRole === 'admin' ? '/BIC2_Mvp/admin.php?section=attendance' : '/BIC2_Mvp/attendance.php'],
    ['key' => 'leaves', 'label' => 'الإجازات', 'href' => '/BIC2_Mvp/leaves.php'],
    ['key' => 'payroll', 'label' => 'الرواتب', 'href' => '/BIC2_Mvp/payroll.php'],
    ['key' => 'notifications', 'label' => 'الإشعارات', 'href' => '/BIC2_Mvp/notifications.php'],
    ['key' => 'reports', 'label' => 'التقارير', 'href' => '/BIC2_Mvp/reports.php'],
];
$heraShellEmployeeLinks = [
    ['key' => 'employee', 'label' => 'الحضور والاستراحة', 'href' => '/BIC2_Mvp/employee.php'],
    ['key' => 'attendance', 'label' => 'سجل الحضور', 'href' => '/BIC2_Mvp/attendance.php'],
    ['key' => 'profile', 'label' => 'ملفي الشخصي', 'href' => '/BIC2_Mvp/profile.php'],
    ['key' => 'leaves', 'label' => 'الإجازات', 'href' => '/BIC2_Mvp/leaves.php'],
    ['key' => 'payroll', 'label' => 'الراتب', 'href' => '/BIC2_Mvp/payroll.php'],
    ['key' => 'notifications', 'label' => 'الإشعارات', 'href' => '/BIC2_Mvp/notifications.php'],
];
$heraShellLinks = in_array($heraShellRole, ['admin', 'hr'], true)
    ? $heraShellManagementLinks
    : $heraShellEmployeeLinks;
$heraShellIcons = [
    'admin' => '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>',
    'overview' => '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>',
    'categories' => '<svg viewBox="0 0 24 24"><path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/></svg>',
    'attendance' => '<svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18m-12 5 2 2 4-4"/></svg>',
    'employees' => '<svg viewBox="0 0 24 24"><path d="M16 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2m2-13a4 4 0 1 0 8 0 4 4 0 0 0-8 0Zm10 1a4 4 0 0 1 0 7m2 5v-2a4 4 0 0 0-3-3.87"/></svg>',
    'settings' => '<svg viewBox="0 0 24 24"><path d="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z"/><path d="m19.4 15 .1.1 1.4 1.1-1.4 2.4-1.7-.6a8 8 0 0 1-1.6.9l-.3 1.8h-2.8l-.3-1.8a8 8 0 0 1-1.6-.9l-1.7.6-1.4-2.4 1.4-1.1a7 7 0 0 1 0-1.9l-1.4-1.1 1.4-2.4 1.7.6a8 8 0 0 1 1.6-.9l.3-1.8h2.8l.3 1.8a8 8 0 0 1 1.6.9l1.7-.6 1.4 2.4-1.4 1.1a7 7 0 0 1 0 1.8Z" transform="translate(-1 -1) scale(1.08)"/></svg>',
    'leaves' => '<svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18m4 8c-4 0-7-2-7-5 4 0 7 2 7 5Zm0 0c0-3 2-5 5-6 0 3-2 6-5 6Z"/></svg>',
    'payroll' => '<svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="15" rx="2"/><path d="M3 9h18m-5 5h2m-15-12h14"/></svg>',
    'notifications' => '<svg viewBox="0 0 24 24"><path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9Zm-8 13h4"/></svg>',
    'reports' => '<svg viewBox="0 0 24 24"><path d="M4 20V10m5 10V4m5 16v-7m5 7V7m-17 14h20"/></svg>',
    'employee' => '<svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>',
    'profile' => '<svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>',
    'logout' => '<svg viewBox="0 0 24 24"><path d="M10 17l5-5-5-5m5 5H3m9-9h7a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-7"/></svg>',
];
?>
<div class="hera-shell-backdrop" data-hera-shell-close hidden></div>
<aside class="hera-shell-sidebar" id="hera-shell-sidebar" aria-label="التنقل الرئيسي">
  <a class="hera-shell-brand" href="/BIC2_Mvp/<?= $heraShellRole === 'hr' ? 'workspace.php' : ($heraShellRole === 'admin' ? 'admin.php' : 'employee.php') ?>" aria-label="HERA منصة الموارد البشرية" title="HERA منصة الموارد البشرية">
    <img src="/BIC2_Mvp/assets/animated-logo.gif" alt="" width="40" height="40" />
    <span><strong>HERA</strong><small>منصة الموارد البشرية</small></span>
  </a>
  <div class="hera-shell-account">
    <span class="hera-shell-avatar" aria-hidden="true"><?= htmlspecialchars(mb_substr($heraShellName ?: 'H', 0, 1), ENT_QUOTES, 'UTF-8') ?></span>
    <span class="hera-shell-account-copy"><strong><?= htmlspecialchars($heraShellName, ENT_QUOTES, 'UTF-8') ?></strong><small><?= $heraShellRole === 'employee' ? 'موظف' : 'فريق الموارد البشرية' ?></small></span>
  </div>
  <?php if ($heraShellRole === 'hr'): ?>
    <a class="hera-shell-workspace-link" href="/BIC2_Mvp/workspace.php" aria-label="مساحات العمل" title="مساحات العمل"><span class="hera-shell-nav-icon" aria-hidden="true"><?= $heraShellIcons['categories'] ?></span><span class="hera-shell-nav-text">مساحات العمل</span><span class="hera-shell-workspace-arrow" aria-hidden="true">↗</span></a>
  <?php endif; ?>
  <nav class="hera-shell-nav" aria-label="أقسام المنصة">
    <p class="hera-shell-nav-label">إدارة الموارد البشرية</p>
    <?php if (in_array($heraShellRole, ['admin', 'hr'], true) && $heraShellPath === 'admin.php'): ?>
      <?php foreach ([['overview', 'نظرة عامة'], ['categories', 'فئات ومجموعات العمل'], ['attendance', 'متابعة الحضور'], ['employees', 'إدارة الموظفين'], ['settings', 'إعدادات الشركة']] as [$sectionKey, $sectionLabel]): ?>
        <button class="hera-shell-nav-link<?= ($sectionKey === 'overview' && $heraShellActive === 'admin') ? ' is-active' : '' ?>" type="button" data-hera-section="<?= $sectionKey ?>" aria-label="<?= htmlspecialchars($sectionLabel, ENT_QUOTES, 'UTF-8') ?>" title="<?= htmlspecialchars($sectionLabel, ENT_QUOTES, 'UTF-8') ?>"<?= ($sectionKey === 'overview' && $heraShellActive === 'admin') ? ' aria-current="page"' : '' ?>>
          <span class="hera-shell-nav-icon" aria-hidden="true"><?= $heraShellIcons[$sectionKey] ?></span><span class="hera-shell-nav-text"><?= htmlspecialchars($sectionLabel, ENT_QUOTES, 'UTF-8') ?></span>
        </button>
      <?php endforeach; ?>
    <?php endif; ?>
    <?php foreach ($heraShellLinks as $heraLink): ?>
      <?php if ($heraShellPath === 'admin.php' && in_array($heraLink['key'], ['admin', 'attendance'], true)) continue; ?>
      <a class="hera-shell-nav-link<?= $heraShellActive === $heraLink['key'] ? ' is-active' : '' ?>" href="<?= $heraLink['href'] ?>" aria-label="<?= htmlspecialchars($heraLink['label'], ENT_QUOTES, 'UTF-8') ?>" title="<?= htmlspecialchars($heraLink['label'], ENT_QUOTES, 'UTF-8') ?>"<?= $heraShellActive === $heraLink['key'] ? ' aria-current="page"' : '' ?>>
        <span class="hera-shell-nav-icon" aria-hidden="true"><?= $heraShellIcons[$heraLink['key']] ?></span>
        <span class="hera-shell-nav-text"><?= htmlspecialchars($heraLink['label'], ENT_QUOTES, 'UTF-8') ?></span>
      </a>
    <?php endforeach; ?>
    <?php if (in_array($heraShellRole, ['admin', 'hr'], true) && $heraShellActive === ''): ?>
      <a class="hera-shell-nav-link" href="/BIC2_Mvp/admin.php" aria-label="لوحة الموارد البشرية" title="لوحة الموارد البشرية"><span class="hera-shell-nav-icon" aria-hidden="true"><?= $heraShellIcons['admin'] ?></span><span class="hera-shell-nav-text">لوحة الموارد البشرية</span></a>
    <?php endif; ?>
  </nav>
  <a class="hera-shell-signout" href="/BIC2_Mvp/logout.php" aria-label="تسجيل الخروج" title="تسجيل الخروج"><span class="hera-shell-nav-icon" aria-hidden="true"><?= $heraShellIcons['logout'] ?></span><span class="hera-shell-nav-text">تسجيل الخروج</span></a>
</aside>
<script src="/BIC2_Mvp/assets/hera-shell.js?v=hera-unified-20261030-5" defer></script>
