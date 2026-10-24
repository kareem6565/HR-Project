<?php
/**
 * api/profile.php
 *
 * GET ?user_id=N → Get comprehensive profile analytics, attendance history,
 *                   GPS logs, and salary & deductions breakdown for employee N.
 */

require_once __DIR__ . '/../includes/db.php';
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/helpers.php';

header('Content-Type: application/json; charset=utf-8');

requireLogin();

$pdo         = getPDO();
$currentUser = getCurrentUser();

// Determine target user ID (Employee can view their own profile, Admin/HR can view any)
$requestedId = isset($_GET['user_id']) ? (int)$_GET['user_id'] : $currentUser['id'];

if ($currentUser['role'] === 'employee' && $requestedId !== (int)$currentUser['id']) {
    jsonResponse(false, 'غير مصرح لك بعرض بيانات موظف آخر.');
}

// Fetch user + category details
$stmt = $pdo->prepare(
    "SELECT u.id, u.emp_code, u.name, u.role, u.basic_salary, u.yearly_vacation_days, u.created_at,
            c.id AS category_id, c.name AS category_name, c.work_start_time, c.work_end_time,
            c.break_start_time, c.break_duration_minutes, c.cutoff_minutes,
            c.center_latitude, c.center_longitude, c.allowed_radius_meters
     FROM users u
     LEFT JOIN categories c ON c.id = u.category_id
     WHERE u.id = ?"
);
$stmt->execute([$requestedId]);
$user = $stmt->fetch();

if (!$user) {
    jsonResponse(false, 'الموظف غير موجود.');
}

// Fetch all attendance logs for this user
$stmtAtt = $pdo->prepare(
    "SELECT date, check_in_time, check_out_time, break_start_time, break_end_time,
            lat_in, lng_in, distance_in_meters, status
     FROM attendance
     WHERE user_id = ?
     ORDER BY date DESC"
);
$stmtAtt->execute([$requestedId]);
$logs = $stmtAtt->fetchAll();

// Statistics calculation
$totalRecords = count($logs);
$countPresent = 0;
$countLate    = 0;
$countAbsent  = 0;

foreach ($logs as $row) {
    if ($row['status'] === 'present') $countPresent++;
    if ($row['status'] === 'late')    $countLate++;
    if ($row['status'] === 'absent')  $countAbsent++;
}

// Financial / Payroll Calculations
$basicSalary  = (float)$user['basic_salary'];
$dailyRate    = $basicSalary / 30.0;

// Deductions: 1 full day per absence, 0.25 day per late day
$absenceDeduction = $countAbsent * $dailyRate;
$lateDeduction    = $countLate * ($dailyRate * 0.25);
$totalDeductions  = $absenceDeduction + $lateDeduction;
$netSalary        = max(0, $basicSalary - $totalDeductions);

jsonResponse(true, 'OK', [
    'user' => [
        'id'                   => (int)$user['id'],
        'emp_code'             => $user['emp_code'],
        'name'                 => $user['name'],
        'role'                 => $user['role'],
        'category_name'        => $user['category_name'] ?? 'عام',
        'work_start_time'      => $user['work_start_time'] ?? '09:00:00',
        'work_end_time'        => $user['work_end_time'] ?? '18:00:00',
        'break_start_time'     => $user['break_start_time'] ?? '13:00:00',
        'break_duration'       => (int)($user['break_duration_minutes'] ?? 60),
        'cutoff_minutes'       => (int)($user['cutoff_minutes'] ?? 60),
        'basic_salary'         => $basicSalary,
        'yearly_vacation_days' => (int)$user['yearly_vacation_days'],
        'created_at'           => $user['created_at'],
    ],
    'stats' => [
        'total_records' => $totalRecords,
        'present_days'  => $countPresent,
        'late_days'     => $countLate,
        'absent_days'   => $countAbsent,
    ],
    'payroll' => [
        'basic_salary'      => round($basicSalary, 2),
        'daily_rate'        => round($dailyRate, 2),
        'absence_deduction' => round($absenceDeduction, 2),
        'late_deduction'    => round($lateDeduction, 2),
        'total_deductions'  => round($totalDeductions, 2),
        'net_salary'        => round($netSalary, 2),
    ],
    'logs' => $logs,
]);
