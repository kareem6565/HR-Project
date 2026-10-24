<?php
/**
 * api/categories.php
 *
 * Admin/HR CRUD for employee categories/groups and bulk employee assignment.
 *
 * GET    ?action=list                  → all categories with employee counts
 * GET    ?action=get&id=N              → single category
 * GET    ?action=category_employees&id=N → employees assigned to category N
 * POST   {action:'create', ...}
 * POST   {action:'update', id, ...}
 * POST   {action:'assign_employees', category_id, user_ids: [...]}
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
        $stmt = $pdo->query("SELECT c.*, COUNT(u.id) AS employee_count 
                             FROM categories c 
                             LEFT JOIN users u ON u.category_id = c.id 
                             GROUP BY c.id 
                             ORDER BY c.name ASC");
        jsonResponse(true, 'OK', ['categories' => $stmt->fetchAll()]);
    }

    if ($action === 'get' && !empty($_GET['id'])) {
        $stmt = $pdo->prepare("SELECT * FROM categories WHERE id = ?");
        $stmt->execute([(int)$_GET['id']]);
        $row = $stmt->fetch();
        if (!$row) jsonResponse(false, 'Category not found.');
        jsonResponse(true, 'OK', ['category' => $row]);
    }

    if ($action === 'category_employees' && !empty($_GET['id'])) {
        $catId = (int)$_GET['id'];
        $stmt  = $pdo->prepare("SELECT id, emp_code, name, role, category_id FROM users WHERE category_id = ? ORDER BY name ASC");
        $stmt->execute([$catId]);
        jsonResponse(true, 'OK', ['employees' => $stmt->fetchAll()]);
    }

    jsonResponse(false, 'Unknown action.');
}

// ── POST handler ──────────────────────────────────────────────────────────────

if ($method === 'POST') {
    $body = json_decode(file_get_contents('php://input'), true);

    if (empty($body['action'])) {
        jsonResponse(false, 'Missing action.');
    }

    $validateGeofence = static function (mixed $lat, mixed $lng, mixed $radius): array {
        if (!isValidGeoPoint($lat, $lng)) {
            jsonResponse(false, 'إحداثيات موقع الفئة غير صحيحة.');
        }
        $radius = (int)$radius;
        if ($radius < 25 || $radius > 10000) {
            jsonResponse(false, 'نطاق الفئة يجب أن يكون بين 25 و10,000 متر.');
        }
        return [(float)$lat, (float)$lng, $radius];
    };

    // ── CREATE ─────────────────────────────────────────────────────────────────
    if ($body['action'] === 'create') {
        if (empty($body['name'])) jsonResponse(false, 'اسم الفئة مطلوب.');

        $shiftType = in_array($body['shift_type'] ?? '', ['day', 'night']) ? $body['shift_type'] : 'day';
        [$lat, $lng, $radius] = $validateGeofence(
            $body['center_latitude'] ?? 24.7136000,
            $body['center_longitude'] ?? 46.6753000,
            $body['allowed_radius_meters'] ?? 300
        );

        $stmt = $pdo->prepare(
            "INSERT INTO categories (
                name, shift_type, work_start_time, work_end_time, break_start_time, break_duration_minutes,
                cutoff_minutes, center_latitude, center_longitude, allowed_radius_meters
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        );
        $stmt->execute([
            trim($body['name']),
            $shiftType,
            $body['work_start_time'] ?? '09:00:00',
            $body['work_end_time'] ?? '18:00:00',
            $body['break_start_time'] ?? '13:00:00',
            (int)($body['break_duration_minutes'] ?? 60),
            (int)($body['cutoff_minutes'] ?? 60),
            $lat,
            $lng,
            $radius,
        ]);

        jsonResponse(true, 'تم إضافة فئة العمل بنجاح.', ['id' => $pdo->lastInsertId()]);
    }

    // ── UPDATE ─────────────────────────────────────────────────────────────────
    if ($body['action'] === 'update') {
        if (empty($body['id'])) jsonResponse(false, 'Missing category ID.');

        $shiftType = in_array($body['shift_type'] ?? '', ['day', 'night']) ? $body['shift_type'] : 'day';
        [$lat, $lng, $radius] = $validateGeofence(
            $body['center_latitude'] ?? null,
            $body['center_longitude'] ?? null,
            $body['allowed_radius_meters'] ?? null
        );

        $stmt = $pdo->prepare(
            "UPDATE categories SET 
                name = ?, shift_type = ?, work_start_time = ?, work_end_time = ?, break_start_time = ?,
                break_duration_minutes = ?, cutoff_minutes = ?, center_latitude = ?,
                center_longitude = ?, allowed_radius_meters = ?
             WHERE id = ?"
        );
        $stmt->execute([
            trim($body['name']),
            $shiftType,
            $body['work_start_time'],
            $body['work_end_time'],
            $body['break_start_time'],
            (int)$body['break_duration_minutes'],
            (int)$body['cutoff_minutes'],
            $lat,
            $lng,
            $radius,
            (int)$body['id'],
        ]);

        jsonResponse(true, 'تم تحديث فئة العمل بنجاح.');
    }

    // ── BULK ASSIGN EMPLOYEES ───────────────────────────────────────────────
    if ($body['action'] === 'assign_employees') {
        if (empty($body['category_id'])) jsonResponse(false, 'معرف الفئة مطلوب.');

        $catId   = (int)$body['category_id'];
        $userIds = is_array($body['user_ids'] ?? null) ? array_map('intval', $body['user_ids']) : [];

        // Unassign all users currently in this category
        $pdo->prepare("UPDATE users SET category_id = NULL WHERE category_id = ?")->execute([$catId]);

        // Assign selected users
        if (!empty($userIds)) {
            $in  = implode(',', array_fill(0, count($userIds), '?'));
            $params = array_merge([$catId], $userIds);
            $stmt = $pdo->prepare("UPDATE users SET category_id = ? WHERE id IN ($in)");
            $stmt->execute($params);
        }

        jsonResponse(true, 'تم تحديث الموظفين التابعين لهذه الفئة بنجاح.');
    }

    // ── DELETE ─────────────────────────────────────────────────────────────────
    if ($body['action'] === 'delete') {
        if (empty($body['id'])) jsonResponse(false, 'Missing category ID.');

        $id = (int)$body['id'];

        $pdo->prepare("DELETE FROM categories WHERE id = ?")->execute([$id]);
        jsonResponse(true, 'تم حذف الفئة بنجاح.');
    }

    jsonResponse(false, 'Unknown action.');
}

jsonResponse(false, 'Method not allowed.');
