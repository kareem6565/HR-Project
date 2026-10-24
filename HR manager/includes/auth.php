<?php
/**
 * Authentication & Authorization helpers.
 * Include this file at the top of every protected page.
 */

if (session_status() === PHP_SESSION_NONE) {
    session_start([
        'cookie_httponly' => true,
        'cookie_samesite' => 'Lax',
    ]);
}

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
    return '/BIC2_Mvp/employee.php';
}

/**
 * Ensure a user is logged in; redirect to login page otherwise.
 */
function requireLogin(): void
{
    if (empty($_SESSION['user_id'])) {
        redirect('/BIC2_Mvp/login.php');
    }
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
