<?php
require_once __DIR__ . '/includes/db.php';
require_once __DIR__ . '/includes/auth.php';
require_once __DIR__ . '/includes/helpers.php';
require_once __DIR__ . '/includes/hr_platform.php';

requireHR();
$actor = getCurrentUser();
$pdo = getPDO(true);
if (empty($_SESSION['policy_admin_csrf'])) {
    $_SESSION['policy_admin_csrf'] = bin2hex(random_bytes(32));
}
$csrf = (string)$_SESSION['policy_admin_csrf'];
$flash = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $postedCsrf = (string)($_POST['csrf'] ?? '');
    if (!hash_equals($csrf, $postedCsrf)) {
        http_response_code(403);
        exit('انتهت صلاحية الجلسة. حدّث الصفحة وحاول مرة أخرى.');
    }
    $action = (string)($_POST['action'] ?? '');
    if ($action === 'save_draft') {
        $title = trim((string)($_POST['policy_title'] ?? ''));
        $section = trim((string)($_POST['section_title'] ?? ''));
        $sectionText = trim((string)($_POST['section_text'] ?? ''));
        $source = trim((string)($_POST['source_name'] ?? ''));
        $reference = trim((string)($_POST['source_reference'] ?? ''));
        $effectiveFrom = trim((string)($_POST['effective_from'] ?? '')) ?: null;
        $effectiveUntil = trim((string)($_POST['effective_until'] ?? '')) ?: null;
        $validDate = static function (?string $value): bool {
            if ($value === null) return true;
            $parsed = DateTime::createFromFormat('!Y-m-d', $value);
            return $parsed instanceof DateTime && $parsed->format('Y-m-d') === $value;
        };
        if ($title === '' || $section === '' || $sectionText === '' || $source === ''
            || mb_strlen($title) > 200 || mb_strlen($section) > 200 || mb_strlen($sectionText) > 20000
            || mb_strlen($source) > 255 || mb_strlen($reference) > 500
            || !$validDate($effectiveFrom) || !$validDate($effectiveUntil)
            || ($effectiveFrom && $effectiveUntil && $effectiveUntil < $effectiveFrom)) {
            $flash = 'راجع الحقول: العنوان والقسم والنص والمصدر مطلوبة، وتأكد من طول النص والتواريخ.';
        } else {
            $insert = $pdo->prepare(
                "INSERT INTO employee_policy_sections
                    (policy_title, section_title, section_text, source_name, source_reference,
                     effective_from, effective_until, status)
                 VALUES (?, ?, ?, ?, ?, ?, ?, 'draft') RETURNING id"
            );
            $insert->execute([$title, $section, $sectionText, $source, $reference ?: null, $effectiveFrom, $effectiveUntil]);
            $id = (int)$insert->fetchColumn();
            auditHRAction($pdo, (int)$actor['id'], 'create_draft', 'employee_policy_section', $id);
            $flash = 'تم حفظ مسودة السياسة. راجعها ثم اعتمدها لتصبح متاحة للمساعد.';
        }
    } elseif ($action === 'approve') {
        $id = (int)($_POST['id'] ?? 0);
        $policy = $pdo->prepare("SELECT * FROM employee_policy_sections WHERE id=? AND status='draft'");
        $policy->execute([$id]);
        $row = $policy->fetch();
        if (!$row) {
            $flash = 'المسودة غير موجودة أو تم التعامل معها بالفعل.';
        } else {
            $pdo->beginTransaction();
            try {
                $archivePrevious = $pdo->prepare(
                    "UPDATE employee_policy_sections SET status='archived', updated_at=CURRENT_TIMESTAMP
                     WHERE policy_title=? AND section_title=? AND status='approved' AND id<>?"
                );
                $archivePrevious->execute([$row['policy_title'], $row['section_title'], $id]);
                $approve = $pdo->prepare(
                    "UPDATE employee_policy_sections SET status='approved', approved_by=?,
                     approved_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='draft'"
                );
                $approve->execute([(int)$actor['id'], $id]);
                auditHRAction($pdo, (int)$actor['id'], 'approve', 'employee_policy_section', $id);
                $pdo->commit();
                $flash = 'تم اعتماد القسم، وسيستخدم المساعد النسخة الحالية فقط.';
            } catch (Throwable $error) {
                $pdo->rollBack();
                error_log('Policy section approval failed: ' . $error->getMessage());
                $flash = 'تعذر اعتماد السياسة. حاول مرة أخرى.';
            }
        }
    } elseif ($action === 'archive') {
        $id = (int)($_POST['id'] ?? 0);
        $archive = $pdo->prepare(
            "UPDATE employee_policy_sections SET status='archived', updated_at=CURRENT_TIMESTAMP
             WHERE id=? AND status IN ('draft','approved')"
        );
        $archive->execute([$id]);
        if ($archive->rowCount()) {
            auditHRAction($pdo, (int)$actor['id'], 'archive', 'employee_policy_section', $id);
            $flash = 'تم أرشفة القسم وإيقاف استخدامه في إجابات المساعد.';
        } else {
            $flash = 'القسم غير موجود أو مؤرشف بالفعل.';
        }
    }
}

$sections = $pdo->query(
    "SELECT p.*, u.name AS approver_name
     FROM employee_policy_sections p
     LEFT JOIN users u ON u.id=p.approved_by
     ORDER BY CASE p.status WHEN 'draft' THEN 0 WHEN 'approved' THEN 1 ELSE 2 END,
              p.policy_title, p.section_title, p.created_at DESC"
)->fetchAll();
?>
<!doctype html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>سياسات الشركة | HERA</title>
  <link rel="stylesheet" href="/BIC2_Mvp/assets/hera-brand.css?v=hera-unified-20261030-7" />
  <style>
    .policy-page { width:min(1100px,100%); margin:auto; padding:28px; color:#e4eeec; }
    .policy-card { margin:18px 0; padding:20px; border:1px solid #ffffff18; border-radius:16px; background:#ffffff08; }
    .policy-form { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; }
    .policy-form label { display:grid; gap:6px; font-size:13px; color:#b6c8c4; }
    .policy-form input,.policy-form textarea { width:100%; padding:10px; border:1px solid #ffffff26; border-radius:9px; color:#fff; background:#0c1719; font:inherit; }
    .policy-form textarea { min-height:145px; resize:vertical; }
    .policy-wide { grid-column:1/-1; }
    .policy-button { padding:9px 14px; border:0; border-radius:9px; color:#fff; background:#286e65; cursor:pointer; font:inherit; }
    .policy-button.secondary { background:#334649; }
    .policy-message { padding:12px; border-radius:10px; background:#173d39; }
    .policy-list { display:grid; gap:12px; }
    .policy-row { padding:14px; border:1px solid #ffffff16; border-radius:12px; background:#0b1517; }
    .policy-row p { white-space:pre-wrap; line-height:1.7; color:#c5d3d0; }
    .policy-meta { color:#94a8a4; font-size:12px; }
    .policy-actions { display:flex; gap:8px; margin-top:10px; }
    @media(max-width:650px){.policy-page{padding:16px}.policy-form{grid-template-columns:1fr}.policy-wide{grid-column:auto}}
  </style>
</head>
<body class="hera-theme min-h-screen flex">
<?php require __DIR__ . '/includes/hera-shell.php'; ?>
<main class="main"><div class="policy-page">
  <h1>سياسات الشركة</h1>
  <p>أضف نصًا من مستند رسمي، ثم اعتمده بعد مراجعته. المساعد لا يستخدم إلا الأقسام المعتمدة والسارية.</p>
  <?php if ($flash !== ''): ?><p class="policy-message" role="status"><?= htmlspecialchars($flash, ENT_QUOTES, 'UTF-8') ?></p><?php endif; ?>
  <section class="policy-card">
    <h2>إضافة مسودة قسم</h2>
    <form method="post" class="policy-form">
      <input type="hidden" name="csrf" value="<?= htmlspecialchars($csrf, ENT_QUOTES, 'UTF-8') ?>" />
      <input type="hidden" name="action" value="save_draft" />
      <label>اسم السياسة<input name="policy_title" maxlength="200" required /></label>
      <label>عنوان القسم<input name="section_title" maxlength="200" required /></label>
      <label class="policy-wide">نص القسم<textarea name="section_text" maxlength="20000" required></textarea></label>
      <label>اسم المصدر أو المستند<input name="source_name" maxlength="255" required /></label>
      <label>رقم الصفحة أو رابط المصدر<input name="source_reference" maxlength="500" /></label>
      <label>ساري من<input type="date" name="effective_from" /></label>
      <label>ساري حتى<input type="date" name="effective_until" /></label>
      <div class="policy-wide"><button class="policy-button" type="submit">حفظ كمسودة</button></div>
    </form>
  </section>
  <section class="policy-card">
    <h2>المسودات والسياسات</h2>
    <div class="policy-list">
      <?php foreach ($sections as $section): ?>
        <article class="policy-row">
          <strong><?= htmlspecialchars($section['policy_title'], ENT_QUOTES, 'UTF-8') ?> — <?= htmlspecialchars($section['section_title'], ENT_QUOTES, 'UTF-8') ?></strong>
          <p><?= htmlspecialchars($section['section_text'], ENT_QUOTES, 'UTF-8') ?></p>
          <div class="policy-meta">
            المصدر: <?= htmlspecialchars($section['source_name'], ENT_QUOTES, 'UTF-8') ?>
            <?= $section['source_reference'] ? ' · ' . htmlspecialchars($section['source_reference'], ENT_QUOTES, 'UTF-8') : '' ?>
            · الحالة: <?= htmlspecialchars($section['status'], ENT_QUOTES, 'UTF-8') ?>
            · السريان: <?= htmlspecialchars((string)($section['effective_from'] ?: 'غير محدد'), ENT_QUOTES, 'UTF-8') ?> – <?= htmlspecialchars((string)($section['effective_until'] ?: 'مستمر'), ENT_QUOTES, 'UTF-8') ?>
          </div>
          <?php if ($section['status'] !== 'archived'): ?>
            <div class="policy-actions">
              <?php if ($section['status'] === 'draft'): ?>
                <form method="post"><input type="hidden" name="csrf" value="<?= htmlspecialchars($csrf, ENT_QUOTES, 'UTF-8') ?>" /><input type="hidden" name="action" value="approve" /><input type="hidden" name="id" value="<?= (int)$section['id'] ?>" /><button class="policy-button" type="submit">اعتماد</button></form>
              <?php endif; ?>
              <form method="post"><input type="hidden" name="csrf" value="<?= htmlspecialchars($csrf, ENT_QUOTES, 'UTF-8') ?>" /><input type="hidden" name="action" value="archive" /><input type="hidden" name="id" value="<?= (int)$section['id'] ?>" /><button class="policy-button secondary" type="submit">أرشفة</button></form>
            </div>
          <?php endif; ?>
        </article>
      <?php endforeach; ?>
      <?php if (!$sections): ?><p>لم تتم إضافة سياسات بعد.</p><?php endif; ?>
    </div>
  </section>
</div></main>
</body>
</html>
