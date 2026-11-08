<?php
/**
 * Authentication & Authorization helpers.
 * Include this file at the top of every protected page.
 */

require_once __DIR__ . '/db.php';

if (session_status() === PHP_SESSION_NONE) {
    $httpsEnabled = (!empty($_SERVER['HTTPS']) && strtolower((string)$_SERVER['HTTPS']) !== 'off')
        || (int)($_SERVER['SERVER_PORT'] ?? 0) === 443
        || filter_var(getenv('HERA_SECURE_COOKIES') ?: false, FILTER_VALIDATE_BOOLEAN);
    session_set_cookie_params([
        'lifetime' => 0,
        'path' => '/',
        'secure' => $httpsEnabled,
        'httponly' => true,
        'samesite' => 'Lax',
    ]);
    session_start([
        'cookie_httponly' => true,
        'cookie_secure' => $httpsEnabled,
        'cookie_path' => '/',
        'cookie_samesite' => 'Lax',
    ]);
}

// Prevent authenticated HTML/API responses from being restored from browser cache.
header('Cache-Control: no-store, no-cache, must-revalidate, private');
header('Pragma: no-cache');
header('Expires: 0');

/**
 * Redirect helper.
 */
function redirect(string $url): never
{
    header('Location: ' . $url);
    exit;
}

/**
 * Pick the correct first page for each role.
 */
function roleHome(string $role): string
{
    if ($role === 'hr') return '/BIC2_Mvp/workspace.php';
    if ($role === 'admin') return '/BIC2_Mvp/admin.php';
    if ($role === 'manager') return '/BIC2_Mvp/leaves.php';
    if ($role === 'employee') return '/BIC2_Mvp/employee.php';
    return '/BIC2_Mvp/login.php';
}

/** Destroy the current server session and expire its browser cookie. */
function destroyAuthSession(): void
{
    $_SESSION = [];
    if (ini_get('session.use_cookies')) {
        $params = session_get_cookie_params();
        setcookie(session_name(), '', [
            'expires' => time() - 42000,
            'path' => $params['path'] ?? '/',
            'domain' => $params['domain'] ?? '',
            'secure' => (bool)($params['secure'] ?? false),
            'httponly' => (bool)($params['httponly'] ?? true),
            'samesite' => $params['samesite'] ?? 'Lax',
        ]);
    }
    if (session_status() === PHP_SESSION_ACTIVE) {
        session_destroy();
    }
}

/**
 * Ensure a user is logged in; redirect to login page otherwise.
 */
function requireLogin(): void
{
    if (empty($_SESSION['user_id'])) {
        redirect('/BIC2_Mvp/login.php');
    }

    // Resolve role, organization membership, and account identity from MySQL
    // on every protected request so changed/deleted accounts take effect now.
    try {
        $stmt = getPDO(true)->prepare(
            'SELECT id, emp_code, name, role FROM users WHERE id = ? LIMIT 1'
        );
        $stmt->execute([(int)$_SESSION['user_id']]);
        $user = $stmt->fetch();
    } catch (Throwable $e) {
        error_log('HR Manager session validation failed: ' . $e->getMessage());
        http_response_code(503);
        exit('Authentication is temporarily unavailable. Please try again later.');
    }

    $validRoles = ['admin', 'hr', 'manager', 'employee'];
    if (!$user || !in_array($user['role'] ?? '', $validRoles, true)) {
        destroyAuthSession();
        redirect('/BIC2_Mvp/login.php');
    }

    $_SESSION['user_id'] = (int)$user['id'];
    $_SESSION['emp_code'] = (string)$user['emp_code'];
    $_SESSION['name'] = (string)$user['name'];
    $_SESSION['role'] = (string)$user['role'];
}

/**
 * Ensure the logged-in user is an Admin or HR manager.
 */
function requireHR(): void
{
    requireLogin();
    $role = $_SESSION['role'] ?? '';
    if ($role !== 'admin' && $role !== 'hr') {
        redirect('/BIC2_Mvp/employee.php');
    }
}

/**
 * Ensure the logged-in user is strictly an Admin.
 */
function requireAdmin(): void
{
    requireLogin();
    if (($_SESSION['role'] ?? '') !== 'admin') {
        redirect('/BIC2_Mvp/employee.php');
    }
}

/**
 * Return the current authenticated user's session data.
 */
function getCurrentUser(): array
{
    return [
        'id'       => $_SESSION['user_id']   ?? 0,
        'name'     => $_SESSION['name']      ?? '',
        'emp_code' => $_SESSION['emp_code']  ?? '',
        'role'     => $_SESSION['role']      ?? '',
    ];
}

/**
 * Log a user into the session.
 */
function loginUser(array $user): void
{
    session_regenerate_id(true);
    $_SESSION['user_id']  = $user['id'];
    $_SESSION['name']     = $user['name'];
    $_SESSION['emp_code'] = $user['emp_code'];
    $_SESSION['role']     = $user['role'];
}
