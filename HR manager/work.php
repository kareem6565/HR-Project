<?php
require_once __DIR__ . '/includes/auth.php';
requireLogin();
$user = getCurrentUser();
$target = in_array($user['role'] ?? '', ['hr','admin'], true) ? '/BIC2_Mvp/admin.php' : '/BIC2_Mvp/employee.php';
header('Location: ' . $target, true, 302);
exit;
