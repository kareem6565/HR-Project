<?php
/**
 * Unified API for the extended HR platform.
 * Covers leave workflows, payroll, notifications and reports.
 */
require_once __DIR__ . '/../includes/db.php';
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/helpers.php';
require_once __DIR__ . '/../includes/hr_platform.php';

header('Content-Type: application/json; charset=utf-8');
requireLogin();

$pdo    = getPDO();
$actor  = getCurrentUser();
$method = $_SERVER['REQUEST_METHOD'];
$action = $_GET['action'] ?? '';

if ($method === 'GET' && in_array($action, ['documents','letters','print_letter'], true)) { http_response_code(410); jsonResponse(false, 'ميزة الوثائق والخطابات غير متاحة.'); }
if ($method === 'POST' && ($_POST['action'] ?? '') === 'upload_document') { http_response_code(410); jsonResponse(false, 'ميزة الوثائق والخطابات غير متاحة.'); }

function requestJson(): array
{
    $body = json_decode(file_get_contents('php://input'), true);
    return is_array($body) ? $body : [];
}

function assertHRAdmin(array $actor): void
{
    if (!isHRPlatformAdmin($actor)) jsonResponse(false, 'هذه العملية متاحة للموارد البشرية أو المدير فقط.');
}

function assertManager(array $actor): void
{
    if (!isHRPlatformManager($actor)) jsonResponse(false, 'هذه العملية تتطلب صلاحية مدير فريق.');
}

function validDateInput(string $date): bool
{
    $d = DateTime::createFromFormat('Y-m-d', $date);
    return $d && $d->format('Y-m-d') === $date;
}

function leaveBalances(PDO $pdo, int $userId, int $year): array
{
    ensureLeaveBalances($pdo, $userId, $year);
    $stmt = $pdo->prepare(
        "SELECT lb.id, lt.id AS leave_type_id, lt.code, lt.name, lt.is_paid,
                lb.entitled_days, lb.used_days, (lb.entitled_days - lb.used_days) AS remaining_days
         FROM leave_balances lb
         JOIN leave_types lt ON lt.id = lb.leave_type_id
         WHERE lb.user_id = ? AND lb.balance_year = ? AND lt.is_active = 1
         ORDER BY lt.name"
    );
    $stmt->execute([$userId, $year]);
    return $stmt->fetchAll();
}

function leaveRows(PDO $pdo, array $actor, string $scope): array
{
    $where = '';
    $params = [];
    if ($scope === 'mine') {
        $where = 'WHERE lr.user_id = ?';
        $params[] = (int)$actor['id'];
    } elseif ($scope === 'team') {
        if (isHRPlatformAdmin($actor)) {
            $where = "WHERE lr.status IN ('pending_manager','pending_hr')";
        } else {
            $where = "WHERE lr.manager_id = ? AND lr.status = 'pending_manager'";
            $params[] = (int)$actor['id'];
        }
    } elseif ($scope === 'all') {
        if (!isHRPlatformAdmin($actor)) return [];
    } else {
        return [];
    }

    $stmt = $pdo->prepare(
        "SELECT lr.*, u.name AS employee_name, u.emp_code, lt.name AS leave_type_name, lt.is_paid,
                m.name AS manager_name, h.name AS hr_name
         FROM leave_requests lr
         JOIN users u ON u.id = lr.user_id
         JOIN leave_types lt ON lt.id = lr.leave_type_id
         LEFT JOIN users m ON m.id = lr.manager_id
         LEFT JOIN users h ON h.id = lr.hr_id
         {$where}
         ORDER BY FIELD(lr.status, 'pending_manager', 'pending_hr', 'approved', 'rejected', 'cancelled'), lr.created_at DESC"
    );
    $stmt->execute($params);
    return $stmt->fetchAll();
}

function notificationRows(PDO $pdo, int $userId): array
{
    $stmt = $pdo->prepare('SELECT * FROM notifications WHERE user_id = ? ORDER BY is_read ASC, created_at DESC LIMIT 100');
    $stmt->execute([$userId]);
    return $stmt->fetchAll();
}

function sendSpreadsheet(string $title, array $headers, array $rows, string $format): never
{
    $safeTitle = preg_replace('/[^A-Za-z0-9_-]/u', '_', $title) ?: 'report';
    if ($format === 'xls') {
        header('Content-Type: application/vnd.ms-excel; charset=utf-8');
        header("Content-Disposition: attachment; filename=\"{$safeTitle}.xls\"");
    } else {
        header('Content-Type: text/html; charset=utf-8');
    }

    echo '<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>' . htmlspecialchars($title) . '</title>';
    echo '<style>body{font-family:Tahoma,Arial,sans-serif;padding:28px;color:#111}h1{font-size:20px}table{width:100%;border-collapse:collapse}th,td{border:1px solid #bbb;padding:8px;text-align:right}th{background:#e0e7ff}.meta{color:#555;margin-bottom:18px}@media print{button{display:none}}</style>';
    echo '</head><body><button onclick="window.print()">حفظ / طباعة PDF</button><h1>' . htmlspecialchars($title) . '</h1><p class="meta">تاريخ الإنشاء: ' . date('Y-m-d H:i') . '</p><table><thead><tr>';
    foreach ($headers as $header) echo '<th>' . htmlspecialchars($header) . '</th>';
    echo '</tr></thead><tbody>';
    foreach ($rows as $row) {
        echo '<tr>';
        foreach ($row as $value) echo '<td>' . htmlspecialchars((string)$value, ENT_QUOTES, 'UTF-8') . '</td>';
        echo '</tr>';
    }
    echo '</tbody></table></body></html>';
    exit;
}

function handleReport(PDO $pdo, array $actor): never
{
    assertHRAdmin($actor);
    $type = $_GET['type'] ?? 'attendance';
    $format = $_GET['format'] ?? 'print';
    if (!in_array($format, ['print', 'xls'], true)) jsonResponse(false, 'صيغة التصدير غير مدعومة.');
    $from = $_GET['from'] ?? date('Y-m-01');
    $to   = $_GET['to'] ?? date('Y-m-t');
    if (!validDateInput($from) || !validDateInput($to) || $from > $to) jsonResponse(false, 'نطاق التاريخ غير صحيح.');

    if ($type === 'attendance') {
        $stmt = $pdo->prepare(
            "SELECT a.date, u.emp_code, u.name, c.name AS category_name, a.check_in_time, a.check_out_time,
                    a.break_start_time, a.break_end_time, a.distance_in_meters, a.status
             FROM attendance a JOIN users u ON u.id=a.user_id
             LEFT JOIN categories c ON c.id=u.category_id
             WHERE a.date BETWEEN ? AND ? ORDER BY a.date DESC, u.name"
        );
        $stmt->execute([$from, $to]);
        $rows = [];
        foreach ($stmt->fetchAll() as $r) $rows[] = [$r['date'], $r['emp_code'], $r['name'], $r['category_name'] ?? 'عام', $r['check_in_time'] ?? '-', $r['check_out_time'] ?? '-', $r['status'], $r['distance_in_meters'] ?? '-'];
        sendSpreadsheet('تقرير الحضور', ['التاريخ', 'الكود', 'الموظف', 'الفئة', 'دخول', 'خروج', 'الحالة', 'المسافة (م)'], $rows, $format);
    }

    if ($type === 'leaves') {
        $stmt = $pdo->prepare(
            "SELECT u.emp_code, u.name, lt.name AS leave_type, lr.start_date, lr.end_date, lr.days_count, lr.status, lr.created_at
             FROM leave_requests lr JOIN users u ON u.id=lr.user_id JOIN leave_types lt ON lt.id=lr.leave_type_id
             WHERE DATE(lr.created_at) BETWEEN ? AND ? ORDER BY lr.created_at DESC"
        );
        $stmt->execute([$from, $to]);
        $rows = [];
        foreach ($stmt->fetchAll() as $r) $rows[] = [$r['emp_code'], $r['name'], $r['leave_type'], $r['start_date'], $r['end_date'], $r['days_count'], $r['status'], $r['created_at']];
        sendSpreadsheet('تقرير الإجازات', ['الكود', 'الموظف', 'نوع الإجازة', 'من', 'إلى', 'الأيام', 'الحالة', 'تاريخ الطلب'], $rows, $format);
    }

    if ($type === 'payroll') {
        $year  = (int)($_GET['year'] ?? date('Y'));
        $month = (int)($_GET['month'] ?? date('n'));
        if (!validPeriod($year, $month)) jsonResponse(false, 'فترة الراتب غير صحيحة.');
        $stmt = $pdo->prepare(
            "SELECT u.emp_code, u.name, pi.basic_salary, pi.allowances, pi.bonuses, pi.commissions, pi.overtime_amount,
                    pi.absence_deductions, pi.late_deductions, pi.other_deductions, pi.net_salary, pr.status
             FROM payroll_items pi JOIN payroll_runs pr ON pr.id=pi.payroll_run_id JOIN users u ON u.id=pi.user_id
             WHERE pr.period_year=? AND pr.period_month=? ORDER BY u.name"
        );
        $stmt->execute([$year, $month]);
        $rows = [];
        foreach ($stmt->fetchAll() as $r) $rows[] = [$r['emp_code'], $r['name'], $r['basic_salary'], $r['allowances'], $r['bonuses'], $r['commissions'], $r['overtime_amount'], $r['absence_deductions'] + $r['late_deductions'] + $r['other_deductions'], $r['net_salary'], $r['status']];
        sendSpreadsheet("مسير رواتب {$month}/{$year}", ['الكود', 'الموظف', 'أساسي', 'بدلات', 'مكافآت', 'عمولات', 'إضافي', 'إجمالي الخصومات', 'الصافي', 'الحالة'], $rows, $format);
    }

    jsonResponse(false, 'نوع التقرير غير مدعوم.');
}

function createPayrollRun(PDO $pdo, array $actor, int $year, int $month): int
{
    if (!validPeriod($year, $month)) jsonResponse(false, 'فترة الراتب غير صحيحة.');
    $check = $pdo->prepare('SELECT id FROM payroll_runs WHERE period_year=? AND period_month=?');
    $check->execute([$year, $month]);
    if ($check->fetch()) jsonResponse(false, 'يوجد مسير رواتب لهذه الفترة بالفعل.');

    $pdo->beginTransaction();
    try {
        $pdo->prepare('INSERT INTO payroll_runs (period_year, period_month, created_by) VALUES (?, ?, ?)')->execute([$year, $month, (int)$actor['id']]);
        $runId = (int)$pdo->lastInsertId();
        $firstDay = sprintf('%04d-%02d-01', $year, $month);
        $lastDay = date('Y-m-t', strtotime($firstDay));
        $employees = $pdo->query("SELECT id, basic_salary FROM users WHERE role IN ('employee','manager','hr') ORDER BY name")->fetchAll();
        $adjustments = $pdo->prepare(
            'SELECT component_type, COALESCE(SUM(amount),0) AS total FROM payroll_adjustments WHERE user_id=? AND period_year=? AND period_month=? GROUP BY component_type'
        );
        $attendance = $pdo->prepare(
            "SELECT SUM(status='absent') AS absences, SUM(status='late') AS lates FROM attendance WHERE user_id=? AND date BETWEEN ? AND ?"
        );
        $insert = $pdo->prepare(
            'INSERT INTO payroll_items (payroll_run_id,user_id,basic_salary,allowances,bonuses,commissions,overtime_amount,absence_deductions,late_deductions,other_deductions,net_salary)
             VALUES (?,?,?,?,?,?,?,?,?,?,?)'
        );

        foreach ($employees as $employee) {
            $components = ['allowance' => 0.0, 'bonus' => 0.0, 'commission' => 0.0, 'overtime' => 0.0, 'deduction' => 0.0];
            $adjustments->execute([(int)$employee['id'], $year, $month]);
            foreach ($adjustments->fetchAll() as $adjustment) $components[$adjustment['component_type']] = (float)$adjustment['total'];

            $attendance->execute([(int)$employee['id'], $firstDay, $lastDay]);
            $att = $attendance->fetch() ?: ['absences' => 0, 'lates' => 0];
            $basic = (float)$employee['basic_salary'];
            $daily = $basic / 30;
            $absenceDeduction = (float)$att['absences'] * $daily;
            $lateDeduction = (float)$att['lates'] * ($daily * 0.25);
            $net = max(0, $basic + $components['allowance'] + $components['bonus'] + $components['commission'] + $components['overtime'] - $absenceDeduction - $lateDeduction - $components['deduction']);
            $insert->execute([$runId, (int)$employee['id'], $basic, $components['allowance'], $components['bonus'], $components['commission'], $components['overtime'], $absenceDeduction, $lateDeduction, $components['deduction'], $net]);
        }

        auditHRAction($pdo, (int)$actor['id'], 'create', 'payroll_run', $runId, ['year' => $year, 'month' => $month]);
        $pdo->commit();
        return $runId;
    } catch (Throwable $e) {
        $pdo->rollBack();
        throw $e;
    }
}

if ($method === 'GET' && $action === 'report') {
    handleReport($pdo, $actor);
}


if ($method === 'GET') {
    if ($action === 'overview') {
        $year = (int)($_GET['year'] ?? date('Y'));
        $unread = $pdo->prepare('SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0');
        $unread->execute([(int)$actor['id']]);
        jsonResponse(true, 'OK', [
            'user' => $actor,
            'balances' => leaveBalances($pdo, (int)$actor['id'], $year),
            'my_leaves' => leaveRows($pdo, $actor, 'mine'),
            'team_leaves' => isHRPlatformManager($actor) ? leaveRows($pdo, $actor, 'team') : [],
            'notifications' => array_slice(notificationRows($pdo, (int)$actor['id']), 0, 8),
            'unread_notifications' => (int)$unread->fetchColumn(),
        ]);
    }

    if ($action === 'leave_types') {
        assertHRAdmin($actor);
        jsonResponse(true, 'OK', ['leave_types' => $pdo->query('SELECT * FROM leave_types ORDER BY is_active DESC, name')->fetchAll()]);
    }

    if ($action === 'all_leaves') {
        assertHRAdmin($actor);
        jsonResponse(true, 'OK', ['requests' => leaveRows($pdo, $actor, 'all')]);
    }

    if ($action === 'payroll_runs') {
        assertHRAdmin($actor);
        $stmt = $pdo->query(
            "SELECT pr.*, u.name AS created_by_name, COUNT(pi.id) AS employee_count, COALESCE(SUM(pi.net_salary),0) AS total_net
             FROM payroll_runs pr JOIN users u ON u.id=pr.created_by LEFT JOIN payroll_items pi ON pi.payroll_run_id=pr.id
             GROUP BY pr.id ORDER BY pr.period_year DESC, pr.period_month DESC"
        );
        jsonResponse(true, 'OK', ['runs' => $stmt->fetchAll()]);
    }

    if ($action === 'my_payslips') {
        $stmt = $pdo->prepare(
            "SELECT pi.*, pr.period_year, pr.period_month, pr.status
             FROM payroll_items pi JOIN payroll_runs pr ON pr.id=pi.payroll_run_id
             WHERE pi.user_id=? AND pr.status='published' ORDER BY pr.period_year DESC, pr.period_month DESC"
        );
        $stmt->execute([(int)$actor['id']]);
        jsonResponse(true, 'OK', ['payslips' => $stmt->fetchAll()]);
    }

    if ($action === 'employees') {
        assertHRAdmin($actor);
        $rows = $pdo->query("SELECT id, emp_code, name, role, manager_id, basic_salary FROM users WHERE role <> 'admin' ORDER BY name")->fetchAll();
        jsonResponse(true, 'OK', ['employees' => $rows]);
    }

    if ($action === 'team_members') {
        assertManager($actor);
        if (isHRPlatformAdmin($actor)) {
            $stmt = $pdo->query(
                "SELECT u.id, u.emp_code, u.name, u.role, m.name AS manager_name, c.name AS category_name
                 FROM users u LEFT JOIN users m ON m.id=u.manager_id LEFT JOIN categories c ON c.id=u.category_id
                 WHERE u.role IN ('employee','manager') ORDER BY m.name, u.name"
            );
        } else {
            $stmt = $pdo->prepare(
                "SELECT u.id, u.emp_code, u.name, u.role, c.name AS category_name
                 FROM users u LEFT JOIN categories c ON c.id=u.category_id WHERE u.manager_id=? ORDER BY u.name"
            );
            $stmt->execute([(int)$actor['id']]);
        }
        jsonResponse(true, 'OK', ['members' => $stmt->fetchAll()]);
    }

    if ($action === 'notifications') {
        jsonResponse(true, 'OK', ['notifications' => notificationRows($pdo, (int)$actor['id'])]);
    }

    jsonResponse(false, 'Unknown action.');
}

if ($method === 'POST') {
    $body = requestJson();
    $action = $body['action'] ?? '';
    if (in_array($action, ['request_letter','handle_letter'], true)) { http_response_code(410); jsonResponse(false, 'ميزة الوثائق والخطابات غير متاحة.'); }

    if ($action === 'submit_leave') {
        if (($actor['role'] ?? '') === 'admin') {
            jsonResponse(false, 'حساب مدير النظام لا يقدّم طلبات إجازة من النظام.');
        }
        $leaveTypeId = (int)($body['leave_type_id'] ?? 0);
        $start = trim($body['start_date'] ?? '');
        $end = trim($body['end_date'] ?? '');
        if (!$leaveTypeId || !validDateInput($start) || !validDateInput($end) || $start > $end) jsonResponse(false, 'بيانات الإجازة غير صحيحة.');
        $days = (int)((strtotime($end) - strtotime($start)) / 86400) + 1;
        $typeStmt = $pdo->prepare('SELECT * FROM leave_types WHERE id=? AND is_active=1');
        $typeStmt->execute([$leaveTypeId]);
        $leaveType = $typeStmt->fetch();
        if (!$leaveType) jsonResponse(false, 'نوع الإجازة غير متاح.');
        $overlap = $pdo->prepare("SELECT id FROM leave_requests WHERE user_id=? AND status IN ('pending_manager','pending_hr','approved') AND start_date<=? AND end_date>=?");
        $overlap->execute([(int)$actor['id'], $end, $start]);
        if ($overlap->fetch()) jsonResponse(false, 'يوجد طلب إجازة متداخل في هذه الفترة.');

        ensureLeaveBalances($pdo, (int)$actor['id'], (int)date('Y', strtotime($start)));
        if ((int)$leaveType['is_paid'] === 1) {
            $balance = $pdo->prepare('SELECT entitled_days-used_days FROM leave_balances WHERE user_id=? AND leave_type_id=? AND balance_year=?');
            $balance->execute([(int)$actor['id'], $leaveTypeId, (int)date('Y', strtotime($start))]);
            if ((float)$balance->fetchColumn() < $days) jsonResponse(false, 'رصيد الإجازة لا يكفي لهذا الطلب.');
        }

        $managerStmt = $pdo->prepare('SELECT manager_id FROM users WHERE id=?');
        $managerStmt->execute([(int)$actor['id']]);
        $managerId = (int)($managerStmt->fetchColumn() ?: 0);
        $status = $managerId && (int)$leaveType['requires_manager_approval'] ? 'pending_manager' : 'pending_hr';
        $stmt = $pdo->prepare('INSERT INTO leave_requests (user_id,leave_type_id,start_date,end_date,days_count,reason,status,manager_id) VALUES (?,?,?,?,?,?,?,?)');
        $stmt->execute([(int)$actor['id'], $leaveTypeId, $start, $end, $days, clean($body['reason'] ?? ''), $status, $managerId ?: null]);
        $requestId = (int)$pdo->lastInsertId();
        if ($status === 'pending_manager') addNotification($pdo, $managerId, 'leave', 'طلب إجازة جديد', "يوجد طلب إجازة جديد بانتظار موافقتك.", '/BIC2_Mvp/notifications.php');
        else notifyRoles($pdo, ['admin', 'hr'], 'leave', 'طلب إجازة جديد', 'يوجد طلب إجازة جديد بانتظار مراجعة الموارد البشرية.', '/BIC2_Mvp/notifications.php');
        auditHRAction($pdo, (int)$actor['id'], 'create', 'leave_request', $requestId);
        jsonResponse(true, 'تم إرسال طلب الإجازة بنجاح.');
    }

    if ($action === 'leave_decision') {
        $requestId = (int)($body['request_id'] ?? 0);
        $decision = $body['decision'] ?? '';
        $comment = clean($body['comment'] ?? '');
        if (!$requestId || !in_array($decision, ['approved', 'rejected'], true)) jsonResponse(false, 'قرار المراجعة غير صحيح.');
        $stmt = $pdo->prepare('SELECT lr.*, lt.name AS leave_type_name, lt.is_paid FROM leave_requests lr JOIN leave_types lt ON lt.id=lr.leave_type_id WHERE lr.id=?');
        $stmt->execute([$requestId]);
        $request = $stmt->fetch();
        if (!$request) jsonResponse(false, 'طلب الإجازة غير موجود.');

        if ($request['status'] === 'pending_manager' && (int)$request['manager_id'] === (int)$actor['id'] && ($actor['role'] ?? '') === 'manager') {
            $next = $decision === 'approved' ? 'pending_hr' : 'rejected';
            $pdo->prepare('UPDATE leave_requests SET status=?, manager_comment=?, manager_action_at=NOW() WHERE id=?')->execute([$next, $comment, $requestId]);
            if ($next === 'pending_hr') notifyRoles($pdo, ['admin', 'hr'], 'leave', 'طلب إجازة بانتظار HR', 'تمت موافقة المدير على طلب إجازة وهو بانتظار قرار HR.', '/BIC2_Mvp/notifications.php');
            else addNotification($pdo, (int)$request['user_id'], 'leave', 'تم رفض طلب الإجازة', 'قام المدير برفض طلب الإجازة. ' . $comment, '/BIC2_Mvp/notifications.php');
        } elseif ($request['status'] === 'pending_hr' && isHRPlatformAdmin($actor)) {
            $pdo->beginTransaction();
            try {
                if ($decision === 'approved' && (int)$request['is_paid'] === 1) {
                    $year = (int)date('Y', strtotime($request['start_date']));
                    ensureLeaveBalances($pdo, (int)$request['user_id'], $year);
                    $balance = $pdo->prepare('UPDATE leave_balances SET used_days=used_days+? WHERE user_id=? AND leave_type_id=? AND balance_year=? AND entitled_days-used_days>=?');
                    $balance->execute([$request['days_count'], $request['user_id'], $request['leave_type_id'], $year, $request['days_count']]);
                    if ($balance->rowCount() !== 1) throw new RuntimeException('رصيد الإجازة لم يعد كافيًا.');
                }
                $pdo->prepare('UPDATE leave_requests SET status=?, hr_id=?, hr_comment=?, hr_action_at=NOW() WHERE id=?')->execute([$decision, (int)$actor['id'], $comment, $requestId]);
                addNotification($pdo, (int)$request['user_id'], 'leave', $decision === 'approved' ? 'تمت الموافقة على الإجازة' : 'تم رفض طلب الإجازة', ($decision === 'approved' ? 'تمت الموافقة على طلب ' : 'تم رفض طلب ') . $request['leave_type_name'] . '. ' . $comment, '/BIC2_Mvp/notifications.php');
                $pdo->commit();
            } catch (Throwable $e) {
                $pdo->rollBack();
                jsonResponse(false, $e->getMessage());
            }
        } else {
            jsonResponse(false, 'لا تملك صلاحية اتخاذ هذا القرار أو أن حالة الطلب تغيّرت.');
        }
        auditHRAction($pdo, (int)$actor['id'], $decision, 'leave_request', $requestId);
        jsonResponse(true, 'تم حفظ قرار الإجازة.');
    }

    if ($action === 'save_leave_type') {
        assertHRAdmin($actor);
        $id = (int)($body['id'] ?? 0);
        $code = strtolower(trim($body['code'] ?? ''));
        $name = trim($body['name'] ?? '');
        if (!preg_match('/^[a-z0-9_]{2,40}$/', $code) || $name === '') jsonResponse(false, 'أدخل رمزًا إنجليزيًا واسمًا صالحين لنوع الإجازة.');
        $values = [$code, clean($name), max(0, (float)($body['default_days'] ?? 0)), !empty($body['is_paid']) ? 1 : 0, !empty($body['requires_manager_approval']) ? 1 : 0, !empty($body['is_active']) ? 1 : 0];
        if ($id) {
            $values[] = $id;
            $pdo->prepare('UPDATE leave_types SET code=?,name=?,default_days=?,is_paid=?,requires_manager_approval=?,is_active=? WHERE id=?')->execute($values);
        } else {
            $pdo->prepare('INSERT INTO leave_types (code,name,default_days,is_paid,requires_manager_approval,is_active) VALUES (?,?,?,?,?,?)')->execute($values);
        }
        jsonResponse(true, 'تم حفظ نوع الإجازة.');
    }

    if ($action === 'assign_manager') {
        assertHRAdmin($actor);
        $employeeId = (int)($body['employee_id'] ?? 0);
        $managerId = !empty($body['manager_id']) ? (int)$body['manager_id'] : null;
        if (!$employeeId || $employeeId === $managerId) jsonResponse(false, 'تعيين المدير غير صحيح.');
        if ($managerId) {
            $check = $pdo->prepare("SELECT id FROM users WHERE id=? AND role='manager'");
            $check->execute([$managerId]);
            if (!$check->fetch()) jsonResponse(false, 'اختر مستخدمًا بصلاحية Manager.');
        }
        $pdo->prepare('UPDATE users SET manager_id=? WHERE id=?')->execute([$managerId, $employeeId]);
        auditHRAction($pdo, (int)$actor['id'], 'assign_manager', 'user', $employeeId, ['manager_id' => $managerId]);
        jsonResponse(true, 'تم تحديث مدير الموظف.');
    }

    if ($action === 'add_adjustment') {
        assertHRAdmin($actor);
        $userId = (int)($body['user_id'] ?? 0);
        $year = (int)($body['year'] ?? 0);
        $month = (int)($body['month'] ?? 0);
        $type = $body['component_type'] ?? '';
        $amount = (float)($body['amount'] ?? 0);
        if (!$userId || !validPeriod($year, $month) || !in_array($type, ['allowance','bonus','commission','overtime','deduction'], true) || $amount <= 0) jsonResponse(false, 'بيانات مكوّن الراتب غير صحيحة.');
        $run = $pdo->prepare('SELECT id FROM payroll_runs WHERE period_year=? AND period_month=?');
        $run->execute([$year, $month]);
        if ($run->fetch()) jsonResponse(false, 'أضف المكونات قبل إنشاء مسير الرواتب لهذه الفترة.');
        $pdo->prepare('INSERT INTO payroll_adjustments (user_id,period_year,period_month,component_type,amount,description,created_by) VALUES (?,?,?,?,?,?,?)')->execute([$userId, $year, $month, $type, $amount, clean($body['description'] ?? ''), (int)$actor['id']]);
        jsonResponse(true, 'تمت إضافة مكوّن الراتب.');
    }

    if ($action === 'create_payroll_run') {
        assertHRAdmin($actor);
        try {
            $runId = createPayrollRun($pdo, $actor, (int)($body['year'] ?? 0), (int)($body['month'] ?? 0));
            jsonResponse(true, 'تم إنشاء مسير رواتب مسودة بنجاح.', ['run_id' => $runId]);
        } catch (Throwable $e) {
            jsonResponse(false, 'تعذر إنشاء المسير: ' . $e->getMessage());
        }
    }

    if ($action === 'publish_payroll_run') {
        assertHRAdmin($actor);
        $runId = (int)($body['run_id'] ?? 0);
        $run = $pdo->prepare("SELECT * FROM payroll_runs WHERE id=? AND status='draft'");
        $run->execute([$runId]);
        $row = $run->fetch();
        if (!$row) jsonResponse(false, 'مسير الرواتب غير موجود أو منشور بالفعل.');
        $pdo->prepare("UPDATE payroll_runs SET status='published',published_by=?,published_at=NOW() WHERE id=?")->execute([(int)$actor['id'], $runId]);
        $users = $pdo->prepare('SELECT user_id FROM payroll_items WHERE payroll_run_id=?');
        $users->execute([$runId]);
        foreach ($users->fetchAll() as $user) addNotification($pdo, (int)$user['user_id'], 'payroll', 'كشف راتب جديد', "تم نشر كشف راتب {$row['period_month']}/{$row['period_year']}.", '/BIC2_Mvp/notifications.php');
        auditHRAction($pdo, (int)$actor['id'], 'publish', 'payroll_run', $runId);
        jsonResponse(true, 'تم نشر مسير الرواتب وإرسال الإشعارات.');
    }

    if ($action === 'mark_notification_read') {
        $id = (int)($body['notification_id'] ?? 0);
        if ($id) $pdo->prepare('UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?')->execute([$id, (int)$actor['id']]);
        else $pdo->prepare('UPDATE notifications SET is_read=1 WHERE user_id=?')->execute([(int)$actor['id']]);
        jsonResponse(true, 'تم تحديث الإشعارات.');
    }

    jsonResponse(false, 'Unknown action.');
}

jsonResponse(false, 'Method not allowed.');
