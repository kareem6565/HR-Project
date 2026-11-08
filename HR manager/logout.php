<?php
require_once __DIR__ . '/includes/auth.php';

$cookie = session_get_cookie_params();
setcookie(session_name(), '', [
    'expires' => time() - 42000,
    'path' => $cookie['path'] ?: '/',
    'domain' => $cookie['domain'],
    'secure' => $cookie['secure'],
    'httponly' => $cookie['httponly'],
    'samesite' => $cookie['samesite'] ?? 'Lax',
]);

$_SESSION = [];
session_destroy();

redirect('/BIC2_Mvp/login.php?logged_out=1');
