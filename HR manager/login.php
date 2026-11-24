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
                $stmt = $pdo->prepare("SELECT * FROM users WHERE emp_code = ? AND (email IS NULL OR email = '') LIMIT 1");
                $stmt->execute([$empCode]);
            } else {
                $stmt = $pdo->prepare('SELECT * FROM users WHERE email = ? LIMIT 1');
                $stmt->execute([$email]);
            }
            $user = $stmt->fetch();

            if ($user && password_verify($password, $user['password_hash'])) {
                loginUser($user);
                if (!empty($user['must_change_password'])) {
                    redirect('/BIC2_Mvp/change_password.php');
                }
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
  <meta name="theme-color" content="#faf7f2" />
  <title>مرحبًا بعودتك — HERA</title>
  <meta name="description" content="سجّل الدخول إلى HERA لمتابعة قرارات توظيف أذكى." />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="/BIC2_Mvp/assets/hera-brand.css?v=hera-motion-20261116-1" />
  <link rel="stylesheet" href="/BIC2_Mvp/assets/login.css?v=hera-login-20261121-1" />
  <script src="/BIC2_Mvp/assets/hera-language.js?v=hera-login-20261121-1" defer></script>
</head>
<body class="hera-auth-page">
  <main class="auth-layout" aria-label="HERA sign in">
    <section class="auth-form-side" aria-labelledby="login-title">
      <div class="auth-form-wrap">
        <a href="/BIC2_Mvp/index.php" class="auth-brand" aria-label="HERA">
          <img src="/BIC2_Mvp/assets/hera-icon-light.svg" alt="" width="48" height="48" />
          <span class="auth-brand-copy"><strong>HERA</strong><span>AI HR &amp; Recruitment</span></span>
        </a>

        <header class="auth-heading">
          <p class="auth-eyebrow">HERA WORKSPACE</p>
          <h1 id="login-title">أهلًا بعودتك</h1>
          <p>سجّل الدخول لمواصلة بناء قرارات توظيف أكثر ذكاءً.</p>
        </header>

        <?php if ($successMessage): ?>
          <div class="auth-alert auth-alert-success" role="status">
            <span aria-hidden="true">✓</span><?= htmlspecialchars($successMessage, ENT_QUOTES, 'UTF-8') ?>
          </div>
        <?php endif; ?>
        <?php if ($error): ?>
          <div class="auth-alert <?= $isServiceError ? 'auth-alert-warning' : 'auth-alert-error' ?>" role="alert">
            <svg aria-hidden="true" viewBox="0 0 24 24" fill="none"><path d="M12 8v4m0 4h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
            <span><?= htmlspecialchars($error, ENT_QUOTES, 'UTF-8') ?></span>
          </div>
        <?php endif; ?>

        <form id="loginForm" method="POST" action="/BIC2_Mvp/login.php" class="auth-form">
          <input type="hidden" name="login_nonce" value="<?= htmlspecialchars($_SESSION['login_nonce'], ENT_QUOTES, 'UTF-8') ?>" />
          <input type="hidden" name="login_mode" id="loginMode" value="<?= htmlspecialchars($loginMode, ENT_QUOTES, 'UTF-8') ?>" />

          <div id="emailLoginField" class="auth-field" <?= $loginMode === 'legacy' ? 'hidden' : '' ?>>
            <label for="email">البريد الإلكتروني</label>
            <input type="email" id="email" name="email" value="<?= htmlspecialchars($email, ENT_QUOTES, 'UTF-8') ?>" placeholder="name@company.com" autocomplete="username" dir="ltr" <?= $loginMode === 'legacy' ? 'disabled' : 'required autofocus' ?> />
          </div>
          <div id="legacyLoginField" class="auth-field" <?= $loginMode !== 'legacy' ? 'hidden' : '' ?>>
            <label for="emp_code">كود الموظف للحسابات القديمة</label>
            <input type="text" id="emp_code" name="emp_code" value="<?= htmlspecialchars($empCode, ENT_QUOTES, 'UTF-8') ?>" autocomplete="username" dir="ltr" <?= $loginMode === 'legacy' ? 'required autofocus' : 'disabled' ?> />
          </div>
          <div class="auth-field">
            <label for="password">كلمة المرور</label>
            <div class="password-control" dir="ltr">
              <input type="password" id="password" name="password" placeholder="••••••••" autocomplete="current-password" required />
              <button type="button" class="password-toggle" id="passwordToggle" aria-label="إظهار كلمة المرور" aria-pressed="false">
                <svg class="eye-open" aria-hidden="true" viewBox="0 0 24 24" fill="none"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z" stroke="currentColor" stroke-width="1.7"/><circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="1.7"/></svg>
                <svg class="eye-closed" aria-hidden="true" viewBox="0 0 24 24" fill="none"><path d="m3 3 18 18M10.6 10.6a2 2 0 0 0 2.8 2.8M9.9 5.2A10.8 10.8 0 0 1 12 5c6.4 0 10 7 10 7a16 16 0 0 1-3.1 3.8M6.2 6.2C3.5 8 2 12 2 12s3.6 7 10 7a10 10 0 0 0 4-.8" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>
              </button>
            </div>
          </div>

          <div class="auth-form-meta">
            <details class="reset-help">
              <summary>نسيت كلمة المرور؟</summary>
              <p>تواصل مع مسؤول الموارد البشرية في شركتك لإعادة تعيين كلمة المرور.</p>
            </details>
          </div>

          <button type="submit" id="loginBtn" class="auth-submit">
            <span class="auth-submit-label">تسجيل الدخول</span>
            <svg aria-hidden="true" viewBox="0 0 24 24" fill="none"><path d="M5 12h14m-6-6 6 6-6 6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </button>
        </form>

        <div class="auth-divider"><span>أو</span></div>
        <button type="button" id="legacyLoginToggle" class="auth-alternate">
          <?= $loginMode === 'legacy' ? 'الدخول بالبريد الإلكتروني' : 'الدخول بكود الموظف لحساب قديم' ?>
        </button>
        <p class="auth-account-note">لا تملك حسابًا؟ تواصل مع مسؤول الموارد البشرية.</p>
        <p class="auth-copyright">© <?= date('Y') ?> HERA · جميع الحقوق محفوظة</p>
      </div>
    </section>

    <aside class="auth-visual" aria-label="HERA intelligent recruitment preview">
      <div class="visual-orbit visual-orbit-one"></div><div class="visual-orbit visual-orbit-two"></div>
      <div class="visual-content">
        <div class="visual-copy">
          <span class="visual-kicker"><span class="kicker-dot"></span> HERA AI RECRUITMENT</span>
          <h2>التوظيف الأذكى يبدأ مع HERA</h2>
          <p>ارتقِ بالتوظيف عبر فحص ذكي للسير الذاتية، ومطابقة دقيقة للمواهب، وقرارات إنسانية مدعومة بالذكاء الاصطناعي.</p>
        </div>

        <div class="product-preview" aria-hidden="true">
          <div class="preview-topbar"><div class="preview-brand"><img src="/BIC2_Mvp/assets/hera-icon-dark.svg" alt="" /><span>Talent insights</span></div><span class="preview-live"><i></i> Live analysis</span></div>
          <div class="preview-body">
            <div class="preview-title-row"><div><span class="preview-overline">CANDIDATE MATCH</span><strong>Senior Product Designer</strong></div><span class="preview-count">12 profiles</span></div>
            <div class="candidate-card candidate-featured">
              <div class="candidate-avatar">SM</div><div class="candidate-info"><strong>Sarah Mitchell</strong><span>Product Designer · 6 years</span><div class="skill-list"><span>Product design</span><span>Figma</span><span>Research</span></div></div>
              <div class="match-score"><span class="score-ring"><b>92</b></span><small>match</small></div>
            </div>
            <div class="insight-card"><span class="insight-icon"><svg viewBox="0 0 24 24" fill="none"><path d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Zm6 11 .9 2.1L21 17l-2.1.9L18 20l-.9-2.1L15 17l2.1-.9L18 14Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg></span><div><strong>Strong experience match</strong><span>5 of 6 role requirements found</span></div><span class="insight-check">✓</span></div>
            <div class="preview-footer"><span><i class="human-dot"></i> Human review enabled</span><span class="preview-progress"><i></i><i></i><i></i><i></i><i></i><i></i><i></i></span></div>
          </div>
          <div class="floating-chip"><span class="floating-check">✓</span><span><b>Skills verified</b><small>Evidence from CV</small></span></div>
          <div class="floating-match"><span>↗</span><div><b>Top match</b><small>Candidate ranked #1</small></div></div>
        </div>
        <div class="visual-bottom"><span>HUMAN-LED · AI-ASSISTED</span><span>HIRING WITH CLARITY</span></div>
      </div>
    </aside>
  </main>

  <script>
    (() => {
      const form = document.getElementById('loginForm');
      const mode = document.getElementById('loginMode');
      const emailField = document.getElementById('emailLoginField');
      const legacyField = document.getElementById('legacyLoginField');
      const email = document.getElementById('email');
      const employeeCode = document.getElementById('emp_code');
      const password = document.getElementById('password');
      const passwordToggle = document.getElementById('passwordToggle');
      const toggleButton = document.getElementById('legacyLoginToggle');
      let loginSubmitting = false;
      const isArabic = () => document.documentElement.lang === 'ar';

      function updatePasswordToggleLabel() {
        const visible = password.type === 'text';
        passwordToggle.setAttribute('aria-pressed', String(visible));
        passwordToggle.setAttribute('aria-label', visible
          ? (isArabic() ? 'إخفاء كلمة المرور' : 'Hide password')
          : (isArabic() ? 'إظهار كلمة المرور' : 'Show password'));
      }
      passwordToggle.addEventListener('click', () => {
        password.type = password.type === 'password' ? 'text' : 'password';
        updatePasswordToggleLabel();
        password.focus();
      });
      window.addEventListener('hera:languagechange', updatePasswordToggleLabel);

      toggleButton.addEventListener('click', () => {
        const useLegacy = mode.value !== 'legacy';
        mode.value = useLegacy ? 'legacy' : 'email';
        emailField.hidden = useLegacy;
        legacyField.hidden = !useLegacy;
        email.disabled = useLegacy;
        email.required = !useLegacy;
        employeeCode.disabled = !useLegacy;
        employeeCode.required = useLegacy;
        toggleButton.textContent = useLegacy
          ? (isArabic() ? 'الدخول بالبريد الإلكتروني' : 'Sign in with email')
          : (isArabic() ? 'الدخول بكود الموظف لحساب قديم' : 'Use employee code for an older account');
        (useLegacy ? employeeCode : email).focus();
      });

      form.addEventListener('submit', (event) => {
        if (loginSubmitting) { event.preventDefault(); return; }
        loginSubmitting = true;
        const button = document.getElementById('loginBtn');
        button.disabled = true;
        button.setAttribute('aria-busy', 'true');
        button.querySelector('.auth-submit-label').textContent = isArabic() ? 'جارٍ التحقق...' : 'Signing in...';
      });
      updatePasswordToggleLabel();
    })();
  </script>
</body>
</html>
