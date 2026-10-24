<?php
/**
 * api/employees.php
 *
 * Admin-only CRUD for the users table with category support.
 *
 * GET    ?action=list          → all employees
 * GET    ?action=get&id=N      → single employee
 * POST   {action:'create', ...}
 * POST   {action:'update', id, ...}
 * POST   {action:'delete', id}
 */

require_once __DIR__ . '/../includes/db.php';
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/helpers.php';

header('Content-Type: application/json; charset=utf-8');

requireHR();

$pdo    = getPDO();
$method = $_SERVER['REQUEST_METHOD'];
$action = $_GET['action'] ?? '';

// ── GET handlers ──────────────────────────────────────────────────────────────

if ($method === 'GET') {

    if ($action === 'list') {
        $stmt = $pdo->query(
            "SELECT u.id, u.emp_code, u.name, u.role, u.category_id, u.manager_id, m.name AS manager_name, c.name AS category_name,
                    u.basic_salary, u.yearly_vacation_days, u.created_at
             FROM users u
             LEFT JOIN categories c ON c.id = u.category_id
             LEFT JOIN users m ON m.id = u.manager_id
             ORDER BY u.role DESC, u.name ASC"
        );
        jsonResponse(true, 'OK', ['employees' => $stmt->fetchAll()]);
    }

    if ($action === 'get' && !empty($_GET['id'])) {
        $stmt = $pdo->prepare(
            "SELECT u.id, u.emp_code, u.name, u.role, u.category_id, u.manager_id, m.name AS manager_name, c.name AS category_name,
                    u.basic_salary, u.yearly_vacation_days
             FROM users u
             LEFT JOIN categories c ON c.id = u.category_id
             LEFT JOIN users m ON m.id = u.manager_id
             WHERE u.id = ?"
        );
        $stmt->execute([(int)$_GET['id']]);
        $row = $stmt->fetch();
        if (!$row) jsonResponse(false, 'Employee not found.');
        jsonResponse(true, 'OK', ['employee' => $row]);
    }

    jsonResponse(false, 'Unknown action.');
}

// ── POST handler ──────────────────────────────────────────────────────────────

if ($method === 'POST') {
    $body = json_decode(file_get_contents('php://input'), true);

    if (empty($body['action'])) {
        jsonResponse(false, 'Missing action.');
    }

    // ── CREATE ─────────────────────────────────────────────────────────────────
    if ($body['action'] === 'create') {
        $required = ['emp_code', 'name', 'password', 'role', 'basic_salary'];
        foreach ($required as $field) {
            if (empty($body[$field])) jsonResponse(false, "الحقل '{$field}' مطلوب.");
        }

        // Check unique emp_code
        $chk = $pdo->prepare("SELECT id FROM users WHERE emp_code = ?");
        $chk->execute([trim($body['emp_code'])]);
        if ($chk->fetch()) jsonResponse(false, 'كود الموظف مستخدم بالفعل.');

        $hash = password_hash($body['password'], PASSWORD_BCRYPT, ['cost' => 12]);
        $categoryId = !empty($body['category_id']) ? (int)$body['category_id'] : null;
        $role = in_array($body['role'] ?? '', ['admin', 'hr', 'manager', 'employee']) ? $body['role'] : 'employee';

        $stmt = $pdo->prepare(
            "INSERT INTO users (emp_code, name, password_hash, role, category_id, basic_salary, yearly_vacation_days)
             VALUES (?, ?, ?, ?, ?, ?, ?)"
        );
        $stmt->execute([
            trim($body['emp_code']),
            trim($body['name']),
            $hash,
            $role,
            $categoryId,
            (float)$body['basic_salary'],
            (int)($body['yearly_vacation_days'] ?? 21),
        ]);

        jsonResponse(true, 'تم إضافة الموظف بنجاح.', ['id' => $pdo->lastInsertId()]);
    }

    // ── UPDATE ─────────────────────────────────────────────────────────────────
    if ($body['action'] === 'update') {
        if (empty($body['id'])) jsonResponse(false, 'Missing employee ID.');

        $fields = [];
        $params = [];

        if (!empty($body['name'])) {
            $fields[] = 'name = ?';
            $params[] = trim($body['name']);
        }
        if (!empty($body['emp_code'])) {
            $fields[] = 'emp_code = ?';
            $params[] = trim($body['emp_code']);
        }
        if (!empty($body['role'])) {
            $fields[] = 'role = ?';
            $params[] = in_array($body['role'], ['admin', 'hr', 'manager', 'employee']) ? $body['role'] : 'employee';
        }
        if (array_key_exists('category_id', $body)) {
            $fields[] = 'category_id = ?';
            $params[] = !empty($body['category_id']) ? (int)$body['category_id'] : null;
        }
        if (isset($body['basic_salary'])) {
            $fields[] = 'basic_salary = ?';
            $params[] = (float)$body['basic_salary'];
        }
        if (isset($body['yearly_vacation_days'])) {
            $fields[] = 'yearly_vacation_days = ?';
            $params[] = (int)$body['yearly_vacation_days'];
        }
        if (!empty($body['password'])) {
            $fields[] = 'password_hash = ?';
            $params[] = password_hash($body['password'], PASSWORD_BCRYPT, ['cost' => 12]);
        }

        if (empty($fields)) jsonResponse(false, 'No fields to update.');

        $params[] = (int)$body['id'];
        $pdo->prepare('UPDATE users SET ' . implode(', ', $fields) . ' WHERE id = ?')
            ->execute($params);

        jsonResponse(true, 'تم تحديث بيانات الموظف.');
    }

    // ── DELETE ─────────────────────────────────────────────────────────────────
    if ($body['action'] === 'delete') {
        if (empty($body['id'])) jsonResponse(false, 'Missing employee ID.');

        $id = (int)$body['id'];

        $currentUser = getCurrentUser();
        if ($id === (int)$currentUser['id']) {
            jsonResponse(false, 'لا يمكنك حذف حسابك الخاص.');
        }

        $pdo->prepare("DELETE FROM users WHERE id = ?")->execute([$id]);
        jsonResponse(true, 'تم حذف الموظف.');
    }

    jsonResponse(false, 'Unknown action.');
}

jsonResponse(false, 'Method not allowed.');
