<?php
/**
 * login.php — Login Page for BIC2 Enterprise
 */
require_once __DIR__ . '/includes/db.php';
require_once __DIR__ . '/includes/auth.php';

// Already logged in?
if (!empty($_SESSION['user_id'])) {
    requireLogin();
    redirect(roleHome((string)($_SESSION['role'] ?? '')));
}

$error = '';
$isServiceError = false;
$successMessage = isset($_GET['logged_out']) ? 'تم تسجيل الخروج بنجاح.' : '';
$email = '';
$empCode = '';
$loginMode = 'email';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $loginMode = ($_POST['login_mode'] ?? '') === 'legacy' ? 'legacy' : 'email';
    $email = strtolower(trim($_POST['email'] ?? ''));
    $empCode = strtoupper(trim($_POST['emp_code'] ?? ''));
    $password = $_POST['password'] ?? '';
    $postedNonce = (string)($_POST['login_nonce'] ?? '');
    $storedNonce = (string)($_SESSION['login_nonce'] ?? '');
    unset($_SESSION['login_nonce']);

    if ($postedNonce === '' || $storedNonce === '' || !hash_equals($storedNonce, $postedNonce)) {
        $error = 'انتهت صلاحية نموذج الدخول. أعد المحاولة.';
    } elseif (($loginMode === 'email' && $email === '') || ($loginMode === 'legacy' && $empCode === '') || $password === '') {
        $error = 'يرجى إدخال بيانات الدخول وكلمة المرور.';
    } else {
        try {
            $pdo  = getPDO(true);
            if ($loginMode === 'legacy') {
                $emailColumn = $pdo->query("SHOW COLUMNS FROM users LIKE 'email'")->fetch();
                $legacyEmailCondition = $emailColumn ? " AND (email IS NULL OR email = '')" : '';
                $stmt = $pdo->prepare('SELECT * FROM users WHERE emp_code = ?' . $legacyEmailCondition . ' LIMIT 1');
                $stmt->execute([$empCode]);
            } else {
                $stmt = $pdo->prepare('SELECT * FROM users WHERE email = ? LIMIT 1');
                $stmt->execute([$email]);
            }
            $user = $stmt->fetch();

            if ($user && password_verify($password, $user['password_hash'])) {
                loginUser($user);
                redirect(roleHome($user['role']));
            }
            $error = $loginMode === 'legacy'
                ? 'كود الموظف أو كلمة المرور غير صحيحة.'
                : 'البريد الإلكتروني أو كلمة المرور غير صحيحة.';
        } catch (Throwable $exception) {
            error_log('HR Manager authentication service unavailable: ' . $exception->getMessage());
            $error = 'خدمة تسجيل الدخول غير متاحة حالياً. حاول مرة أخرى لاحقاً.';
            $isServiceError = true;
        }
    }
}

$_SESSION['login_nonce'] = bin2hex(random_bytes(32));
?>
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>تسجيل الدخول — HERA</title>
  <meta name="description" content="تسجيل الدخول إلى منصة HERA لإدارة الموارد البشرية والتوظيف." />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800;900&display=swap" rel="stylesheet" />
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      theme: {
        extend: {
          fontFamily: { cairo: ['Cairo', 'sans-serif'] },
          colors: {
            primary: { 50:'#eff6ff',100:'#dbeafe',200:'#bfdbfe',300:'#93c5fd',400:'#60a5fa',500:'#3b82f6',600:'#2563eb',700:'#1d4ed8',800:'#1e40af',900:'#1e3a8a' },
            dark: { 800:'#1e293b', 900:'#0f172a', 950:'#020617' },
          },
          backdropBlur: { xs: '2px' },
        }
      }
    }
  </script>
  <style>
    * { font-family: 'Cairo', sans-serif; }
    body {
      background: radial-gradient(circle at 50% 0%, #315759 0%, #1B3A3A 62%, #122b2b 100%);
      min-height: 100vh;
    }
    .card-glass {
      background: rgba(15, 23, 42, 0.75);
      backdrop-filter: blur(20px);
      border: 1px solid rgba(255, 255, 255, 0.1);
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);
    }
    .btn-gradient {
      background: linear-gradient(135deg, #1B3A3A 0%, #315759 100%);
      box-shadow: 0 4px 20px rgba(27, 58, 58, 0.35);
      transform: skewX(-4deg);
      transition: all 0.25s ease;
    }
    .btn-gradient:hover {
      transform: skewX(-4deg) translateY(-2px);
      box-shadow: 0 8px 25px rgba(27, 58, 58, 0.5);
    }
    .btn-content {
      transform: skewX(4deg);
    }
    .skew-badge {
      transform: skewX(-8deg);
      display: inline-block;
    }
    .skew-badge-inner {
      transform: skewX(8deg);
      display: inline-block;
    }
  </style>
  <link rel="stylesheet" href="/BIC2_Mvp/assets/hera-brand.css" />
  <script src="/BIC2_Mvp/assets/hera-language.js" defer></script>
</head>
<body class="hera-auth-page flex items-center justify-center p-4">

  <div class="w-full max-w-md">
    
    <!-- Top Brand Logo -->
    <div class="text-center mb-8">
      <a href="/BIC2_Mvp/index.php" class="inline-flex items-center gap-3" aria-label="HERA">
        <img src="/BIC2_Mvp/assets/hera-logo.svg" alt="HERA" class="w-44 h-auto" />
      </a>
    </div>

    <!-- Login Card -->
    <div class="card-glass rounded-3xl p-8 border border-white/10">
      
      <div class="mb-6">
        <h1 class="text-xl font-bold text-white mb-1">تسجيل الدخول للنظام</h1>
          <p class="text-xs text-slate-400">أدخل بريدك الإلكتروني وكلمة المرور الخاصة بك</p>
      </div>

      <?php if ($successMessage): ?>
        <div role="status" class="mb-6 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/25 text-emerald-800 text-sm font-semibold">
          <?= htmlspecialchars($successMessage, ENT_QUOTES, 'UTF-8') ?>
        </div>
      <?php endif; ?>

      <?php if ($error): ?>
        <div role="alert" class="mb-6 p-4 rounded-xl <?= $isServiceError ? 'bg-amber-500/10 border-amber-500/25 text-amber-900' : 'bg-red-500/10 border-red-500/25 text-red-800' ?> border text-sm font-semibold flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
          <span><?= htmlspecialchars($error) ?></span>
        </div>
      <?php endif; ?>

      <form id="loginForm" method="POST" action="/BIC2_Mvp/login.php" class="space-y-4">
        <input type="hidden" name="login_nonce" value="<?= htmlspecialchars($_SESSION['login_nonce'], ENT_QUOTES, 'UTF-8') ?>" />
        <input type="hidden" name="login_mode" id="loginMode" value="<?= $loginMode ?>" />
        <div id="emailLoginField" <?= $loginMode === 'legacy' ? 'hidden' : '' ?>>
          <label for="email" class="block text-xs font-bold text-slate-300 mb-1.5">البريد الإلكتروني</label>
          <input
            type="email"
            id="email"
            name="email"
            value="<?= htmlspecialchars($email, ENT_QUOTES, 'UTF-8') ?>"
            placeholder="name@company.com"
            autocomplete="username"
            <?= $loginMode === 'legacy' ? 'disabled' : 'required autofocus' ?>
            class="w-full px-4 py-3 bg-slate-900/90 border border-slate-700 rounded-xl text-white placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
          />
        </div>

        <div id="legacyLoginField" <?= $loginMode !== 'legacy' ? 'hidden' : '' ?>>
          <label for="emp_code" class="block text-xs font-bold text-slate-300 mb-1.5">كود الموظف للحسابات القديمة</label>
          <input type="text" id="emp_code" name="emp_code" value="<?= htmlspecialchars($empCode, ENT_QUOTES, 'UTF-8') ?>" autocomplete="username" <?= $loginMode === 'legacy' ? 'required autofocus' : 'disabled' ?> class="w-full px-4 py-3 bg-slate-900/90 border border-slate-700 rounded-xl text-white placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all font-mono" />
        </div>

        <div>
          <label for="password" class="block text-xs font-bold text-slate-300 mb-1.5">كلمة المرور</label>
          <input
            type="password"
            id="password"
            name="password"
            placeholder="••••••••"
            autocomplete="current-password"
            required
            class="w-full px-4 py-3 bg-slate-900/90 border border-slate-700 rounded-xl text-white placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
          />
        </div>

        <button type="submit" id="loginBtn" class="w-full py-3.5 rounded-xl font-bold text-white text-sm btn-gradient mt-2 flex items-center justify-center gap-2">
          <span class="btn-content flex items-center gap-2">
            <span>تسجيل الدخول</span>
            <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 rotate-180" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/></svg>
          </span>
        </button>
      </form>

      <button type="button" id="legacyLoginToggle" class="mt-4 w-full text-center text-xs text-slate-500 hover:text-teal-700 underline underline-offset-4">
        <?= $loginMode === 'legacy' ? 'الدخول بالبريد الإلكتروني' : 'حساب قديم بدون بريد؟ ادخل بكود الموظف مؤقتاً' ?>
      </button>

      <div class="mt-5 text-center">
        <a href="/BIC2_Mvp/index.php" class="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition-colors">
          <span>← العودة للواجهة التعريفية للمؤسسات (Landing Page)</span>
        </a>
      </div>

    </div>

    <p class="text-center text-slate-500 text-xs mt-6">© <?= date('Y') ?> منصة BIC2 — جميع الحقوق محفوظة</p>
  </div>

  <script>
    let loginSubmitting = false;
    document.getElementById('legacyLoginToggle').addEventListener('click', function () {
      const useLegacy = document.getElementById('loginMode').value !== 'legacy';
      document.getElementById('loginMode').value = useLegacy ? 'legacy' : 'email';
      document.getElementById('emailLoginField').hidden = useLegacy;
      document.getElementById('legacyLoginField').hidden = !useLegacy;
      document.getElementById('email').disabled = useLegacy;
      document.getElementById('email').required = !useLegacy;
      document.getElementById('emp_code').disabled = !useLegacy;
      document.getElementById('emp_code').required = useLegacy;
      document.getElementById('legacyLoginToggle').textContent = useLegacy
        ? 'الدخول بالبريد الإلكتروني'
        : 'حساب قديم بدون بريد؟ ادخل بكود الموظف مؤقتاً';
    });
    document.getElementById('loginForm').addEventListener('submit', function (event) {
      if (loginSubmitting) {
        event.preventDefault();
        return;
      }
      loginSubmitting = true;
      const btn = document.getElementById('loginBtn');
      btn.innerHTML = `<span class="btn-content flex items-center gap-2"><svg class="animate-spin w-4 h-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"></path></svg> جارٍ التحقق...</span>`;
      btn.disabled = true;
    });
  </script>
</body>
</html>
