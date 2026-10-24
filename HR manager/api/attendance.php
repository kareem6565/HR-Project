<?php
/**
 * api/attendance.php
 *
 * GET  ?action=history            → logged-in employee's recent logs
 * GET  ?action=today_all          → admin/HR: all records for today
 * GET  ?action=user_category      → category details for current employee
 * POST {action:'checkin', lat, lng} → check-in / check-out (supports Day & Night/Cross-Midnight Shifts)
 * POST {action:'break_in'}        → start break
 * POST {action:'break_out'}       → end break
 */

require_once __DIR__ . '/../includes/db.php';
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/helpers.php';
require_once __DIR__ . '/../includes/hr_platform.php';

header('Content-Type: application/json; charset=utf-8');

requireLogin();

// Temporary testing switch: allow check-in at any time of day.
// Set to true again before production to enforce each category's cutoff window.
const ENFORCE_CHECKIN_CUTOFF = false;

$pdo    = getPDO();
$user   = getCurrentUser();
$method = $_SERVER['REQUEST_METHOD'];
$action = $_GET['action'] ?? '';

// Helper to find open attendance record (today or yesterday for night shifts)
function getOpenAttendanceRecord(\PDO $pdo, int $userId): ?array
{
    $today     = date('Y-m-d');
    $yesterday = date('Y-m-d', strtotime('-1 day'));

    $stmt = $pdo->prepare(
        "SELECT * FROM attendance
         WHERE user_id = ? AND check_out_time IS NULL AND date IN (?, ?)
         ORDER BY date DESC LIMIT 1"
    );
    $stmt->execute([$userId, $today, $yesterday]);
    $rec = $stmt->fetch();

    return $rec ?: null;
}

function locationFromRequest(array $body): array
{
    $lat = $body['lat'] ?? null;
    $lng = $body['lng'] ?? null;
    if (!isValidGeoPoint($lat, $lng)) {
        jsonResponse(false, 'يرجى إرسال إحداثيات موقع صحيحة.');
    }
    return [(float)$lat, (float)$lng];
}

function distanceFromCategory(float $lat, float $lng, array $category): int
{
    return (int)round(haversineDistance($lat, $lng, (float)$category['center_latitude'], (float)$category['center_longitude']));
}

function requireInsideGeofence(float $lat, float $lng, array $category): int
{
    $distance = distanceFromCategory($lat, $lng, $category);
    if ($distance > (int)$category['allowed_radius_meters']) {
        jsonResponse(false, "أنت خارج نطاق العمل المسموح ({$category['name']}). المسافة: {$distance} متر (المسموح: {$category['allowed_radius_meters']} متر).", ['distance' => $distance]);
    }
    return $distance;
}

function addGeofenceEvent(PDO $pdo, int $userId, ?int $attendanceId, string $eventType, float $lat, float $lng, int $distance): void
{
    $stmt = $pdo->prepare(
        'INSERT INTO geofence_events (user_id, attendance_id, event_type, lat, lng, distance_meters) VALUES (?, ?, ?, ?, ?, ?)'
    );
    $stmt->execute([$userId, $attendanceId, $eventType, $lat, $lng, $distance]);
}

function alertGeofenceTransition(PDO $pdo, array $user, string $eventType, int $distance, int $radius): void
{
    try {
        if ($eventType === 'left_geofence') {
            notifyRoles(
                $pdo,
                ['admin', 'hr'],
                'geofence',
                'تنبيه خروج من نطاق الشركة',
                "الموظف {$user['name']} خرج من نطاق الشركة. المسافة الحالية: {$distance} م (المسموح: {$radius} م).",
                '/BIC2_Mvp/admin.php'
            );
        }
    } catch (Throwable) {
        // Attendance must continue if the optional notification service is unavailable.
    }
}

function assertBreakStartWindow(array $category, array $record, DateTime $now): void
{
    $window = getShiftWindow($record['date'], $category['work_start_time'], $category['work_end_time']);
    $breakStart = getShiftScheduledTime($record['date'], $category['work_start_time'], $category['work_end_time'], $category['break_start_time']);
    if ($now < $breakStart) {
        jsonResponse(false, 'لم يحن موعد الاستراحة بعد (تبدأ الاستراحة الساعة ' . substr($category['break_start_time'], 0, 5) . ').');
    }
    if ($now > $window['end']) {
        jsonResponse(false, 'انتهى وقت الدوام؛ لا يمكن بدء استراحة جديدة.');
    }
}

// ── GET handlers ──────────────────────────────────────────────────────────────

if ($method === 'GET') {

    if ($action === 'user_category') {
        $category = getUserCategory($pdo, $user['id']);
        jsonResponse(true, 'OK', ['category' => $category]);
    }

    if ($action === 'history') {
        $stmt = $pdo->prepare(
            "SELECT date, check_in_time, check_out_time, break_start_time, break_end_time, distance_in_meters, status
             FROM attendance
             WHERE user_id = ?
             ORDER BY date DESC
             LIMIT 30"
        );
        $stmt->execute([$user['id']]);
        jsonResponse(true, 'OK', ['records' => $stmt->fetchAll()]);
    }

    if ($action === 'today_all') {
        requireHR();
        $today     = date('Y-m-d');
        $yesterday = date('Y-m-d', strtotime('-1 day'));

        $stmt = $pdo->prepare(
            "SELECT a.id, u.name, u.emp_code, c.name AS category_name,
                    a.date, a.check_in_time, a.check_out_time,
                    a.break_start_time, a.break_end_time,
                    a.lat_in, a.lng_in, a.lat_out, a.lng_out,
                    a.distance_in_meters, a.distance_out_meters,
                    a.last_lat, a.last_lng, a.last_location_at,
                    a.geofence_status, a.break_overrun_minutes, a.status
             FROM attendance a
             JOIN users u ON u.id = a.user_id
             LEFT JOIN categories c ON c.id = u.category_id
             WHERE a.date = ? OR (a.date = ? AND a.check_out_time IS NULL)
             ORDER BY a.date DESC, a.check_in_time ASC"
        );
        $stmt->execute([$today, $yesterday]);
        jsonResponse(true, 'OK', ['records' => $stmt->fetchAll()]);
    }

    if ($action === 'summary_today') {
        requireHR();
        $today = date('Y-m-d');

        $total = $pdo->query("SELECT COUNT(*) FROM users WHERE role='employee'")->fetchColumn();

        $stmtP = $pdo->prepare("SELECT COUNT(*) FROM attendance WHERE date=? AND status='present'");
        $stmtP->execute([$today]);

        $stmtL = $pdo->prepare("SELECT COUNT(*) FROM attendance WHERE date=? AND status='late'");
        $stmtL->execute([$today]);

        $stmtA = $pdo->prepare("SELECT COUNT(*) FROM attendance WHERE date=? AND status='absent'");
        $stmtA->execute([$today]);

        jsonResponse(true, 'OK', [
            'total'   => (int)$total,
            'present' => (int)$stmtP->fetchColumn(),
            'late'    => (int)$stmtL->fetchColumn(),
            'absent'  => (int)$stmtA->fetchColumn(),
        ]);
    }

    if ($action === 'geofence_events') {
        requireHR();
        $date = $_GET['date'] ?? date('Y-m-d');
        $dateObject = DateTime::createFromFormat('Y-m-d', $date);
        if (!$dateObject || $dateObject->format('Y-m-d') !== $date) {
            jsonResponse(false, 'صيغة التاريخ يجب أن تكون YYYY-MM-DD.');
        }

        $stmt = $pdo->prepare(
            "SELECT g.id, g.event_type, g.distance_meters, g.created_at,
                    u.name, u.emp_code, a.date AS attendance_date
             FROM geofence_events g
             JOIN users u ON u.id = g.user_id
             LEFT JOIN attendance a ON a.id = g.attendance_id
             WHERE DATE(g.created_at) = ?
             ORDER BY g.created_at DESC
             LIMIT 200"
        );
        $stmt->execute([$date]);
        jsonResponse(true, 'OK', ['events' => $stmt->fetchAll()]);
    }

    jsonResponse(false, 'Unknown action.');
}

// ── POST handler (Check-in / Check-out / Break) ──────────────────────────────

if ($method === 'POST') {
    $body = json_decode(file_get_contents('php://input'), true);

    if (empty($body['action'])) {
        jsonResponse(false, 'Invalid request.');
    }

    $today        = date('Y-m-d');
    $now          = date('H:i:s');
    $userCategory = getUserCategory($pdo, $user['id']);

    // Check if there is an active open record for user (handles Night Shifts open from yesterday)
    $openRecord = getOpenAttendanceRecord($pdo, $user['id']);

    // ── Action: break_in (Start Break) ────────────────────────────────────────
    if ($body['action'] === 'break_in') {
        if (!$openRecord) {
            jsonResponse(false, 'يجب تسجيل الدخول أولاً قبل بدء الاستراحة.');
        }
        if ($openRecord['break_start_time'] !== null) {
            jsonResponse(false, 'لقد قمت ببدء الاستراحة بالفعل.');
        }
        [$lat, $lng] = locationFromRequest($body);
        $distance = requireInsideGeofence($lat, $lng, $userCategory);
        assertBreakStartWindow($userCategory, $openRecord, new DateTime());

        $upd = $pdo->prepare(
            "UPDATE attendance
             SET break_start_time = ?, last_lat = ?, last_lng = ?, last_location_at = NOW(), geofence_status = 'inside'
             WHERE id = ?"
        );
        $upd->execute([$now, $lat, $lng, $openRecord['id']]);
        addGeofenceEvent($pdo, (int)$user['id'], (int)$openRecord['id'], 'break_started_inside', $lat, $lng, $distance);
        jsonResponse(true, 'تم بدء الاستراحة داخل نطاق الشركة ☕', ['time' => $now, 'distance' => $distance]);
    }

    // ── Action: break_out (End Break) ─────────────────────────────────────────
    if ($body['action'] === 'break_out') {
        if (!$openRecord || $openRecord['break_start_time'] === null) {
            jsonResponse(false, 'لم تقم ببدء الاستراحة بعد.');
        }
        if ($openRecord['break_end_time'] !== null) {
            jsonResponse(false, 'لقد أنهيت الاستراحة بالفعل.');
        }
        [$lat, $lng] = locationFromRequest($body);
        $distance = requireInsideGeofence($lat, $lng, $userCategory);

        $breakStart = getShiftScheduledTime(
            $openRecord['date'],
            $userCategory['work_start_time'],
            $userCategory['work_end_time'],
            $openRecord['break_start_time']
        );
        $elapsedMinutes = max(0, (int)floor((time() - $breakStart->getTimestamp()) / 60));
        $overrunMinutes = max(0, $elapsedMinutes - (int)$userCategory['break_duration_minutes']);

        $upd = $pdo->prepare(
            "UPDATE attendance
             SET break_end_time = ?, break_overrun_minutes = ?, last_lat = ?, last_lng = ?,
                 last_location_at = NOW(), geofence_status = 'inside'
             WHERE id = ?"
        );
        $upd->execute([$now, $overrunMinutes, $lat, $lng, $openRecord['id']]);
        addGeofenceEvent($pdo, (int)$user['id'], (int)$openRecord['id'], 'break_ended_inside', $lat, $lng, $distance);
        jsonResponse(
            true,
            $overrunMinutes > 0 ? "تم إنهاء الاستراحة. تجاوزت المدة المحددة بـ {$overrunMinutes} دقيقة." : 'تم إنهاء الاستراحة والعودة للعمل 💻',
            ['time' => $now, 'distance' => $distance, 'break_overrun_minutes' => $overrunMinutes]
        );
    }

    // ── Action: location_ping (Live geofence monitoring while portal is open) ──
    if ($body['action'] === 'location_ping') {
        if (!$openRecord) {
            jsonResponse(true, 'لا توجد وردية مفتوحة للتتبع.', ['tracking' => false]);
        }
        [$lat, $lng] = locationFromRequest($body);
        $distance = distanceFromCategory($lat, $lng, $userCategory);
        $isInside = $distance <= (int)$userCategory['allowed_radius_meters'];
        $previousStatus = $openRecord['geofence_status'] ?? 'unknown';
        $newStatus = $isInside ? 'inside' : 'outside';
        $event = null;

        if ($newStatus !== $previousStatus) {
            $event = $newStatus === 'outside' ? 'left_geofence' : 'returned_to_geofence';
            addGeofenceEvent($pdo, (int)$user['id'], (int)$openRecord['id'], $event, $lat, $lng, $distance);
            if ($event === 'left_geofence') {
                alertGeofenceTransition($pdo, $user, $event, $distance, (int)$userCategory['allowed_radius_meters']);
            }
        }

        $upd = $pdo->prepare(
            'UPDATE attendance SET last_lat=?, last_lng=?, last_location_at=NOW(), geofence_status=? WHERE id=?'
        );
        $upd->execute([$lat, $lng, $newStatus, $openRecord['id']]);
        jsonResponse(
            true,
            $isInside ? 'أنت داخل نطاق الشركة.' : 'تم تسجيل خروجك من نطاق الشركة وإرسال تنبيه للإدارة.',
            ['tracking' => true, 'inside' => $isInside, 'distance' => $distance, 'allowed_radius' => (int)$userCategory['allowed_radius_meters'], 'event' => $event]
        );
    }

    // ── Action: checkin (Check-in / Check-out) ────────────────────────────────
    if ($body['action'] === 'checkin') {
        [$lat, $lng] = locationFromRequest($body);
        $distance = requireInsideGeofence($lat, $lng, $userCategory);

        // If there is an open record -> Perform Check-Out!
        if ($openRecord) {
            $isNightShift = (
                ($userCategory['shift_type'] ?? '') === 'night' ||
                $userCategory['work_end_time'] < $userCategory['work_start_time'] ||
                $userCategory['work_start_time'] === '00:00:00' ||
                $userCategory['work_start_time'] >= '18:00:00'
            );

            // Validate shift end time for checkout
            $canCheckout = false;
            if ($isNightShift) {
                if ($userCategory['work_start_time'] === '00:00:00') {
                    // For midnight shift 00:00 to 09:00, checkout is valid in the morning from 09:00 AM to 14:00 PM
                    if ($now >= $userCategory['work_end_time'] && $now <= '14:00:00') {
                        $canCheckout = true;
                    }
                } else {
                    if ($now >= $userCategory['work_end_time'] && $now < $userCategory['work_start_time']) {
                        $canCheckout = true;
                    }
                }
            } else {
                if ($now >= $userCategory['work_end_time']) {
                    $canCheckout = true;
                }
            }

            if (!$canCheckout) {
                jsonResponse(false, 'لم يحن موعد الانصراف بعد (ينتهي الدوام الساعة ' . substr($userCategory['work_end_time'], 0, 5) . ').');
            }

            // Close break automatically if open
            if ($openRecord['break_start_time'] !== null && $openRecord['break_end_time'] === null) {
                $breakStart = getShiftScheduledTime(
                    $openRecord['date'],
                    $userCategory['work_start_time'],
                    $userCategory['work_end_time'],
                    $openRecord['break_start_time']
                );
                $elapsedMinutes = max(0, (int)floor((time() - $breakStart->getTimestamp()) / 60));
                $overrunMinutes = max(0, $elapsedMinutes - (int)$userCategory['break_duration_minutes']);
                $pdo->prepare(
                    "UPDATE attendance SET break_end_time = ?, break_overrun_minutes = ? WHERE id = ?"
                )->execute([$now, $overrunMinutes, $openRecord['id']]);
            }

            // Punch Out
            $upd = $pdo->prepare(
                "UPDATE attendance
                 SET check_out_time = ?, lat_out = ?, lng_out = ?, distance_out_meters = ?,
                     last_lat = ?, last_lng = ?, last_location_at = NOW(), geofence_status = 'inside'
                 WHERE id = ?"
            );
            $upd->execute([$now, $lat, $lng, $distance, $lat, $lng, $openRecord['id']]);
            addGeofenceEvent($pdo, (int)$user['id'], (int)$openRecord['id'], 'checkout_inside', $lat, $lng, $distance);
            jsonResponse(true, 'تم تسجيل الانصراف بنجاح 👋', ['type' => 'checkout', 'time' => $now, 'distance' => $distance]);
        }

        // No open record -> Perform Check-In!

        // Determine if Night Shift
        $isNightShift = (
            ($userCategory['shift_type'] ?? '') === 'night' ||
            $userCategory['work_end_time'] < $userCategory['work_start_time'] ||
            $userCategory['work_start_time'] === '00:00:00' ||
            $userCategory['work_start_time'] >= '18:00:00'
        );

        // Check-in Cutoff Time Validation
        $workStartTS = strtotime($today . ' ' . $userCategory['work_start_time']);
        $cutoffTS    = $workStartTS + ($userCategory['cutoff_minutes'] * 60);
        $nowTS       = strtotime($today . ' ' . $now);

        // Special handling for 00:00 (Midnight) shift or Night shifts
        if ($userCategory['work_start_time'] === '00:00:00') {
            // If checking in between 20:00 PM and 23:59 PM (early check-in for midnight shift)
            if ($now >= '20:00:00') {
                $shiftDate   = date('Y-m-d', strtotime('+1 day'));
                $workStartTS = strtotime($shiftDate . ' 00:00:00');
                $cutoffTS    = $workStartTS + ($userCategory['cutoff_minutes'] * 60);
                $nowTS       = strtotime($today . ' ' . $now);
            } else {
                $shiftDate   = $today;
                $workStartTS = strtotime($today . ' 00:00:00');
                $cutoffTS    = $workStartTS + ($userCategory['cutoff_minutes'] * 60);
            }
        } elseif ($isNightShift && $now < $userCategory['work_start_time'] && $now < $userCategory['work_end_time']) {
            $yesterday   = date('Y-m-d', strtotime('-1 day'));
            $workStartTS = strtotime($yesterday . ' ' . $userCategory['work_start_time']);
            $cutoffTS    = $workStartTS + ($userCategory['cutoff_minutes'] * 60);
            $shiftDate   = $yesterday;
        } else {
            $shiftDate   = $today;
        }

        // Verify cutoff limit only when the production rule is enabled.
        if (ENFORCE_CHECKIN_CUTOFF && $nowTS > $cutoffTS) {
            jsonResponse(
                false,
                "عفواً، انتهت المهلة المحددة لتسجيل الحضور لهذا اليوم (موعد الدوام: " . substr($userCategory['work_start_time'], 0, 5) . " — المهلة: " . $userCategory['cutoff_minutes'] . " دقيقة)."
            );
        }

        // Determine status ('present' vs 'late')
        $status = ($nowTS > $workStartTS) ? 'late' : 'present';

        // Check if record already exists for shiftDate
        $chkStmt = $pdo->prepare("SELECT id FROM attendance WHERE user_id = ? AND date = ?");
        $chkStmt->execute([$user['id'], $shiftDate]);
        if ($chkStmt->fetch()) {
            jsonResponse(false, 'لقد سجّلت الحضور والانصراف لهذا الشفت بالفعل.');
        }

        $ins = $pdo->prepare(
            "INSERT INTO attendance (user_id, date, check_in_time, lat_in, lng_in, distance_in_meters, last_lat, last_lng, last_location_at, geofence_status, status)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, NOW(), 'inside', ?)"
        );
        $ins->execute([$user['id'], $shiftDate, $now, $lat, $lng, $distance, $lat, $lng, $status]);
        addGeofenceEvent($pdo, (int)$user['id'], (int)$pdo->lastInsertId(), 'checkin_inside', $lat, $lng, $distance);
        jsonResponse(true, 'تم تسجيل الحضور بنجاح ✅', ['type' => 'checkin', 'time' => $now, 'distance' => $distance, 'status' => $status]);
    }

    jsonResponse(false, 'Unknown action.');
}

jsonResponse(false, 'Method not allowed.');
