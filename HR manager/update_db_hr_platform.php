<?php
/**
 * One-time migration for leave, manager, payroll, documents and notifications.
 * Run once after deploying the extended HR module.
 */
require_once __DIR__ . '/includes/db.php';

function hasColumn(PDO $pdo, string $table, string $column): bool
{
    $stmt = $pdo->query("SHOW COLUMNS FROM `{$table}` LIKE " . $pdo->quote($column));
    return (bool)$stmt->fetch();
}

try {
    $pdo = getPDO();
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

    $pdo->exec("ALTER TABLE users MODIFY COLUMN role ENUM('admin','hr','manager','employee') NOT NULL DEFAULT 'employee'");
    if (!hasColumn($pdo, 'users', 'manager_id')) {
        $pdo->exec('ALTER TABLE users ADD COLUMN manager_id INT UNSIGNED NULL AFTER category_id');
        $pdo->exec('ALTER TABLE users ADD INDEX idx_users_manager (manager_id)');
        $pdo->exec('ALTER TABLE users ADD CONSTRAINT fk_users_manager FOREIGN KEY (manager_id) REFERENCES users(id) ON DELETE SET NULL');
    }

    $pdo->exec("CREATE TABLE IF NOT EXISTS leave_types (
        id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        code VARCHAR(40) NOT NULL UNIQUE,
        name VARCHAR(100) NOT NULL,
        default_days DECIMAL(5,2) NOT NULL DEFAULT 0,
        is_paid TINYINT(1) NOT NULL DEFAULT 1,
        requires_manager_approval TINYINT(1) NOT NULL DEFAULT 1,
        is_active TINYINT(1) NOT NULL DEFAULT 1,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");

    $pdo->exec("CREATE TABLE IF NOT EXISTS leave_balances (
        id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        user_id INT UNSIGNED NOT NULL,
        leave_type_id INT UNSIGNED NOT NULL,
        balance_year SMALLINT UNSIGNED NOT NULL,
        entitled_days DECIMAL(5,2) NOT NULL DEFAULT 0,
        used_days DECIMAL(5,2) NOT NULL DEFAULT 0,
        UNIQUE KEY uq_leave_balance (user_id, leave_type_id, balance_year),
        CONSTRAINT fk_leave_balance_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        CONSTRAINT fk_leave_balance_type FOREIGN KEY (leave_type_id) REFERENCES leave_types(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");

    $pdo->exec("CREATE TABLE IF NOT EXISTS leave_requests (
        id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        user_id INT UNSIGNED NOT NULL,
        leave_type_id INT UNSIGNED NOT NULL,
        start_date DATE NOT NULL,
        end_date DATE NOT NULL,
        days_count DECIMAL(5,2) NOT NULL,
        reason TEXT NULL,
        status ENUM('pending_manager','pending_hr','approved','rejected','cancelled') NOT NULL DEFAULT 'pending_hr',
        manager_id INT UNSIGNED NULL,
        manager_comment TEXT NULL,
        manager_action_at DATETIME NULL,
        hr_id INT UNSIGNED NULL,
        hr_comment TEXT NULL,
        hr_action_at DATETIME NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_leave_request_status (status),
        INDEX idx_leave_request_user_date (user_id, start_date),
        CONSTRAINT fk_leave_request_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        CONSTRAINT fk_leave_request_type FOREIGN KEY (leave_type_id) REFERENCES leave_types(id),
        CONSTRAINT fk_leave_request_manager FOREIGN KEY (manager_id) REFERENCES users(id) ON DELETE SET NULL,
        CONSTRAINT fk_leave_request_hr FOREIGN KEY (hr_id) REFERENCES users(id) ON DELETE SET NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");

    $pdo->exec("CREATE TABLE IF NOT EXISTS payroll_runs (
        id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        period_year SMALLINT UNSIGNED NOT NULL,
        period_month TINYINT UNSIGNED NOT NULL,
        status ENUM('draft','published') NOT NULL DEFAULT 'draft',
        created_by INT UNSIGNED NOT NULL,
        published_by INT UNSIGNED NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        published_at DATETIME NULL,
        UNIQUE KEY uq_payroll_period (period_year, period_month),
        CONSTRAINT fk_payroll_run_creator FOREIGN KEY (created_by) REFERENCES users(id),
        CONSTRAINT fk_payroll_run_publisher FOREIGN KEY (published_by) REFERENCES users(id) ON DELETE SET NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");

    $pdo->exec("CREATE TABLE IF NOT EXISTS payroll_adjustments (
        id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        user_id INT UNSIGNED NOT NULL,
        period_year SMALLINT UNSIGNED NOT NULL,
        period_month TINYINT UNSIGNED NOT NULL,
        component_type ENUM('allowance','bonus','commission','overtime','deduction') NOT NULL,
        amount DECIMAL(12,2) NOT NULL,
        description VARCHAR(255) NOT NULL,
        created_by INT UNSIGNED NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_adjustment_period (period_year, period_month),
        CONSTRAINT fk_adjustment_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        CONSTRAINT fk_adjustment_creator FOREIGN KEY (created_by) REFERENCES users(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");

    $pdo->exec("CREATE TABLE IF NOT EXISTS payroll_items (
        id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        payroll_run_id INT UNSIGNED NOT NULL,
        user_id INT UNSIGNED NOT NULL,
        basic_salary DECIMAL(12,2) NOT NULL DEFAULT 0,
        allowances DECIMAL(12,2) NOT NULL DEFAULT 0,
        bonuses DECIMAL(12,2) NOT NULL DEFAULT 0,
        commissions DECIMAL(12,2) NOT NULL DEFAULT 0,
        overtime_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
        absence_deductions DECIMAL(12,2) NOT NULL DEFAULT 0,
        late_deductions DECIMAL(12,2) NOT NULL DEFAULT 0,
        other_deductions DECIMAL(12,2) NOT NULL DEFAULT 0,
        net_salary DECIMAL(12,2) NOT NULL DEFAULT 0,
        notes TEXT NULL,
        UNIQUE KEY uq_payroll_item (payroll_run_id, user_id),
        CONSTRAINT fk_payroll_item_run FOREIGN KEY (payroll_run_id) REFERENCES payroll_runs(id) ON DELETE CASCADE,
        CONSTRAINT fk_payroll_item_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");

    $pdo->exec("CREATE TABLE IF NOT EXISTS employee_documents (
        id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        user_id INT UNSIGNED NOT NULL,
        document_type VARCHAR(80) NOT NULL,
        title VARCHAR(150) NOT NULL,
        file_path VARCHAR(255) NOT NULL,
        issued_date DATE NULL,
        expiry_date DATE NULL,
        uploaded_by INT UNSIGNED NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_document_user (user_id),
        CONSTRAINT fk_document_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        CONSTRAINT fk_document_uploader FOREIGN KEY (uploaded_by) REFERENCES users(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");

    $pdo->exec("CREATE TABLE IF NOT EXISTS hr_letters (
        id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        user_id INT UNSIGNED NOT NULL,
        letter_type VARCHAR(100) NOT NULL,
        request_note TEXT NULL,
        letter_content MEDIUMTEXT NULL,
        status ENUM('pending','generated','rejected') NOT NULL DEFAULT 'pending',
        handled_by INT UNSIGNED NULL,
        handled_at DATETIME NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT fk_letter_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        CONSTRAINT fk_letter_handler FOREIGN KEY (handled_by) REFERENCES users(id) ON DELETE SET NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");

    $pdo->exec("CREATE TABLE IF NOT EXISTS notifications (
        id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        user_id INT UNSIGNED NOT NULL,
        type VARCHAR(50) NOT NULL DEFAULT 'system',
        title VARCHAR(160) NOT NULL,
        body TEXT NOT NULL,
        link VARCHAR(255) NULL,
        is_read TINYINT(1) NOT NULL DEFAULT 0,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_notification_user (user_id, is_read, created_at),
        CONSTRAINT fk_notification_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");

    $pdo->exec("CREATE TABLE IF NOT EXISTS audit_logs (
        id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        actor_id INT UNSIGNED NULL,
        action VARCHAR(100) NOT NULL,
        entity_type VARCHAR(80) NOT NULL,
        entity_id INT UNSIGNED NULL,
        details JSON NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_audit_entity (entity_type, entity_id),
        CONSTRAINT fk_audit_actor FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE SET NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");

    $seed = $pdo->prepare(
        'INSERT IGNORE INTO leave_types (code, name, default_days, is_paid, requires_manager_approval) VALUES (?, ?, ?, ?, ?)'
    );
    foreach ([
        ['annual', 'إجازة سنوية', 21, 1, 1],
        ['sick', 'إجازة مرضية', 14, 1, 1],
        ['unpaid', 'إجازة بدون راتب', 0, 0, 1],
        ['emergency', 'إجازة طارئة', 3, 1, 1],
    ] as $type) {
        $seed->execute($type);
    }

    $uploadDir = __DIR__ . '/uploads/hr_documents';
    if (!is_dir($uploadDir)) mkdir($uploadDir, 0775, true);

    echo "HR platform migration completed successfully.\n";
} catch (Throwable $e) {
    http_response_code(500);
    echo 'Migration error: ' . $e->getMessage() . "\n";
}
