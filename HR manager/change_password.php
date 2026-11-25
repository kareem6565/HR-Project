<?php
require_once __DIR__ . '/includes/db.php';
require_once __DIR__ . '/includes/auth.php';

requireLogin();

$error = '';
$userId = (int)($_SESSION['user_id'] ?? 0);
$nonce = bin2hex(random_bytes(32));
$_SESSION['password_change_nonce'] = $nonce;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $postedNonce = (string)($_POST['password_change_nonce'] ?? '');
    $storedNonce = (string)($_SESSION['password_change_nonce'] ?? '');
    unset($_SESSION['password_change_nonce']);
    $newPassword = (string)($_POST['new_password'] ?? '');
    $confirmation = (string)($_POST['confirm_password'] ?? '');

    if ($postedNonce === '' || $storedNonce === '' || !hash_equals($storedNonce, $postedNonce)) {
        $error = 'انتهت صلاحية النموذج. أعد المحاولة.';
    } elseif (strlen($newPassword) < 8) {
        $error = 'يجب أن تتكون كلمة المرور الجديدة من 8 أحرف على الأقل.';
    } elseif (in_array(strtolower($newPassword), ['password', '12345678', 'admin123', 'hr123', 'qwerty', 'changeme'], true)) {
        $error = 'اختر كلمة مرور أقوى وغير شائعة.';
    } elseif (!hash_equals($newPassword, $confirmation)) {
        $error = 'كلمتا المرور غير متطابقتين.';
    } else {
        try {
            $pdo = getPDO(true);
            $statement = $pdo->prepare('SELECT password_hash FROM users WHERE id = ? LIMIT 1');
            $statement->execute([$userId]);
            $user = $statement->fetch();

            if (!$user) {
                destroyAuthSession();
                redirect('/BIC2_Mvp/login.php');
            }
            if (password_verify($newPassword, $user['password_hash'])) {
                $error = 'اختر كلمة مرور مختلفة عن كلمة المرور الحالية.';
            } else {
                $update = $pdo->prepare(
                    'UPDATE users SET password_hash = ?, must_change_password = FALSE WHERE id = ?'
                );
                $update->execute([
                    password_hash($newPassword, PASSWORD_BCRYPT, ['cost' => 12]),
                    $userId,
                ]);
                $_SESSION['must_change_password'] = false;
                session_regenerate_id(true);
                redirect(roleHome((string)($_SESSION['role'] ?? '')));
            }
        } catch (Throwable $exception) {
            error_log('HR Manager password change failed: ' . $exception->getMessage());
            $error = 'تعذر تحديث كلمة المرور حالياً. حاول مرة أخرى.';
        }
    }

    $_SESSION['password_change_nonce'] = bin2hex(random_bytes(32));
    $nonce = $_SESSION['password_change_nonce'];
}
?>
<!doctype html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>تغيير كلمة المرور — HERA</title>
  <link rel="stylesheet" href="/BIC2_Mvp/assets/hera-brand.css" />
  <style>
    body { min-height: 100vh; margin: 0; display: grid; place-items: center; padding: 24px; background: #0c1916; color: #f4f7f5; font-family: Inter, Cairo, sans-serif; }
    main { width: min(100%, 440px); padding: 32px; border: 1px solid #304640; border-radius: 20px; background: #14231f; box-shadow: 0 24px 70px #0005; }
    h1 { margin: 0 0 8px; font-size: 1.55rem; }
    p { color: #aebdb7; line-height: 1.7; }
    label { display: block; margin: 18px 0 7px; font-weight: 650; }
    input { box-sizing: border-box; width: 100%; padding: 12px 14px; border: 1px solid #435950; border-radius: 10px; background: #0e1a17; color: inherit; font: inherit; }
    input:focus-visible, button:focus-visible { outline: 3px solid #eadb79; outline-offset: 2px; }
    button { width: 100%; margin-top: 22px; padding: 13px; border: 0; border-radius: 10px; background: #e8d879; color: #10201b; font: inherit; font-weight: 750; cursor: pointer; }
    .error { padding: 10px 12px; border: 1px solid #8b4545; border-radius: 10px; color: #ffc6c6; background: #3b2022; }
    @media (max-width: 520px) { main { padding: 24px; } }
  </style>
</head>
<body>
  <main>
    <h1>غيّر كلمة المرور</h1>
    <p>كلمة المرور الحالية مؤقتة. حدّثها للمتابعة إلى مساحة العمل.</p>
    <?php if ($error !== ''): ?><p class="error" role="alert"><?= htmlspecialchars($error, ENT_QUOTES, 'UTF-8') ?></p><?php endif; ?>
    <form method="post" autocomplete="on">
      <input type="hidden" name="password_change_nonce" value="<?= htmlspecialchars($nonce, ENT_QUOTES, 'UTF-8') ?>" />
      <label for="new_password">كلمة المرور الجديدة</label>
      <input id="new_password" name="new_password" type="password" minlength="8" autocomplete="new-password" required />
      <label for="confirm_password">تأكيد كلمة المرور</label>
      <input id="confirm_password" name="confirm_password" type="password" minlength="8" autocomplete="new-password" required />
      <button type="submit">حفظ ومتابعة</button>
    </form>
    <p><a href="/BIC2_Mvp/logout.php" style="color:#b7d9cf">تسجيل الخروج</a></p>
  </main>
</body>
</html>
