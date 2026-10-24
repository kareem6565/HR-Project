<?php
/**
 * Shared services for the extended HR modules.
 */

function isHRPlatformAdmin(array $user): bool
{
    return in_array($user['role'] ?? '', ['admin', 'hr'], true);
}

function isHRPlatformManager(array $user): bool
{
    return in_array($user['role'] ?? '', ['admin', 'hr', 'manager'], true);
}

function requireManagerAccess(): void
{
    requireLogin();
    if (!isHRPlatformManager(getCurrentUser())) {
        redirect('/BIC2_Mvp/employee.php');
    }
}

function requireHRPlatformAdmin(): void
{
    requireLogin();
    if (!isHRPlatformAdmin(getCurrentUser())) {
        redirect('/BIC2_Mvp/employee.php');
    }
}

function addNotification(PDO $pdo, int $userId, string $type, string $title, string $body, ?string $link = null): void
{
    $stmt = $pdo->prepare(
        'INSERT INTO notifications (user_id, type, title, body, link) VALUES (?, ?, ?, ?, ?)'
    );
    $stmt->execute([$userId, $type, clean($title), clean($body), $link]);
}

function notifyRoles(PDO $pdo, array $roles, string $type, string $title, string $body, ?string $link = null): void
{
    if (!$roles) return;
    $placeholders = implode(',', array_fill(0, count($roles), '?'));
    $stmt = $pdo->prepare("SELECT id FROM users WHERE role IN ({$placeholders})");
    $stmt->execute($roles);
    foreach ($stmt->fetchAll() as $user) {
        addNotification($pdo, (int)$user['id'], $type, $title, $body, $link);
    }
}

function auditHRAction(PDO $pdo, int $actorId, string $action, string $entityType, ?int $entityId = null, array $details = []): void
{
    $stmt = $pdo->prepare(
        'INSERT INTO audit_logs (actor_id, action, entity_type, entity_id, details) VALUES (?, ?, ?, ?, ?)'
    );
    $stmt->execute([$actorId, $action, $entityType, $entityId, json_encode($details, JSON_UNESCAPED_UNICODE)]);
}

function ensureLeaveBalances(PDO $pdo, int $userId, int $year): void
{
    $userStmt = $pdo->prepare('SELECT yearly_vacation_days FROM users WHERE id = ?');
    $userStmt->execute([$userId]);
    $user = $userStmt->fetch();
    if (!$user) return;

    $types = $pdo->query('SELECT id, code, default_days FROM leave_types WHERE is_active = 1')->fetchAll();
    $insert = $pdo->prepare(
        'INSERT IGNORE INTO leave_balances (user_id, leave_type_id, balance_year, entitled_days, used_days)
         VALUES (?, ?, ?, ?, 0)'
    );

    foreach ($types as $type) {
        $entitled = $type['code'] === 'annual' ? (float)$user['yearly_vacation_days'] : (float)$type['default_days'];
        $insert->execute([$userId, (int)$type['id'], $year, $entitled]);
    }
}

function employeeCanBeManagedBy(PDO $pdo, array $actor, int $employeeId): bool
{
    if (isHRPlatformAdmin($actor)) return true;
    if (($actor['role'] ?? '') !== 'manager') return false;

    $stmt = $pdo->prepare('SELECT 1 FROM users WHERE id = ? AND manager_id = ?');
    $stmt->execute([$employeeId, (int)$actor['id']]);
    return (bool)$stmt->fetchColumn();
}

function validPeriod(int $year, int $month): bool
{
    return $year >= 2020 && $year <= 2100 && $month >= 1 && $month <= 12;
}
