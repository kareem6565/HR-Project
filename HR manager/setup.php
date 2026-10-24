<?php
/**
 * setup.php — One-click database initializer.
 *
 * Visit http://localhost/BIC2_Mvp/setup.php to create the database,
 * tables, and seed data automatically.
 */

$host    = 'localhost';
$user    = 'root';
$pass    = '';
$charset = 'utf8mb4';

$messages = [];
$success  = false;

if ($_SERVER['REQUEST_METHOD'] === 'POST' && ($_POST['action'] ?? '') === 'install') {

    try {
        // 1. Connect without selecting a database
        $pdo = new PDO("mysql:host={$host};charset={$charset}", $user, $pass, [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        ]);

        // 2. Read and execute the schema SQL
        $sql = file_get_contents(__DIR__ . '/database/schema.sql');

        if (!$sql) {
            throw new RuntimeException('Unable to read database/schema.sql');
        }

        // Execute multi-statement SQL
        $pdo->exec($sql);

        $messages[] = ['type' => 'success', 'text' => '✅ تم إنشاء قاعدة البيانات والجداول بنجاح!'];
        $messages[] = ['type' => 'success', 'text' => '✅ تم إدراج البيانات التجريبية.'];
        $messages[] = ['type' => 'info',    'text' => '🔑 مدير النظام: ADM001 / admin123'];
        $messages[] = ['type' => 'info',    'text' => '👤 موظف تجريبي: EMP001 / emp123'];
        $success = true;

    } catch (PDOException $e) {
        $messages[] = ['type' => 'error', 'text' => '❌ خطأ في قاعدة البيانات: ' . $e->getMessage()];
    } catch (RuntimeException $e) {
        $messages[] = ['type' => 'error', 'text' => '❌ ' . $e->getMessage()];
    }
}
?>
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>إعداد النظام — Attendance System Setup</title>
  <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&display=swap" rel="stylesheet" />
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    * { font-family: 'Tajawal', sans-serif; }
    body { background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 50%, #0f172a 100%); min-height: 100vh; }
    .glass { background: rgba(255,255,255,.07); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,.12); }
  </style>
  <link rel="stylesheet" href="/BIC2_Mvp/assets/hera-brand.css" />
  <script src="/BIC2_Mvp/assets/hera-language.js" defer></script>
</head>
<body class="flex items-center justify-center min-h-screen p-4">
  <div class="w-full max-w-lg">
    <div class="text-center mb-8">
      <div class="inline-flex items-center justify-center w-20 h-20 glass rounded-2xl mb-4">
        <svg xmlns="http://www.w3.org/2000/svg" class="w-10 h-10 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
      </div>
      <h1 class="text-3xl font-bold text-white">إعداد قاعدة البيانات</h1>
      <p class="text-blue-300 mt-2 text-sm">سيتم إنشاء الجداول وإدراج البيانات التجريبية تلقائياً</p>
    </div>

    <div class="glass rounded-2xl p-8 space-y-6">

      <?php if (!empty($messages)): ?>
        <div class="space-y-3">
          <?php foreach ($messages as $msg):
            $bg = match($msg['type']) {
              'success' => 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300',
              'error'   => 'bg-red-500/20 border-red-500/40 text-red-300',
              default   => 'bg-blue-500/20 border-blue-500/40 text-blue-300',
            };
          ?>
            <div class="<?= $bg ?> border rounded-xl p-3 text-sm"><?= htmlspecialchars($msg['text']) ?></div>
          <?php endforeach; ?>
        </div>
      <?php endif; ?>

      <?php if ($success): ?>
        <a href="/BIC2_Mvp/index.php"
           class="block text-center bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-bold rounded-xl py-3 hover:from-blue-500 hover:to-indigo-500 transition-all">
          🚀 انتقل إلى صفحة تسجيل الدخول
        </a>
      <?php else: ?>
        <div class="space-y-3">
          <div class="bg-white/5 border border-white/10 rounded-xl p-4 text-sm text-slate-300">
            <p class="font-semibold text-white mb-2">المتطلبات:</p>
            <ul class="space-y-1 list-disc list-inside text-xs text-slate-400">
              <li>تأكد من تشغيل خدمة <strong>Apache</strong> و <strong>MySQL</strong> في XAMPP</li>
              <li>اسم المستخدم الافتراضي: <code class="text-blue-300">root</code> بدون كلمة مرور</li>
              <li>سيتم إنشاء قاعدة بيانات <code class="text-blue-300">attendance_db</code> تلقائياً</li>
            </ul>
          </div>

          <form method="POST">
            <input type="hidden" name="action" value="install" />
            <button type="submit"
                    class="w-full bg-gradient-to-r from-emerald-600 to-teal-600 text-white font-bold rounded-xl py-3.5 hover:from-emerald-500 hover:to-teal-500 transition-all flex items-center justify-center gap-2 text-lg">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
              تثبيت قاعدة البيانات
            </button>
          </form>
        </div>
      <?php endif; ?>
    </div>

    <p class="text-center text-blue-400/40 text-xs mt-6">Attendance System — Setup Wizard</p>
  </div>
</body>
</html>
