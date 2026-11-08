<?php
/**
 * update_db_hr.php — Migration script for HR role support.
 */
require_once __DIR__ . '/includes/db.php';
require_once __DIR__ . '/includes/auth.php';

requireHR();

try {
    $pdo = getPDO();

    // Update role ENUM in users table to include 'hr'
    $pdo->exec("ALTER TABLE `users` MODIFY COLUMN `role` ENUM('admin', 'hr', 'employee') NOT NULL DEFAULT 'employee'");

    // Add optional email login for existing accounts without forcing data loss.
    $emailColumn = $pdo->query("SHOW COLUMNS FROM `users` LIKE 'email'")->fetch();
    if (!$emailColumn) {
        $pdo->exec("ALTER TABLE `users` ADD COLUMN `email` VARCHAR(255) NULL DEFAULT NULL AFTER `emp_code`");
    }
    $emailIndex = $pdo->query("SHOW INDEX FROM `users` WHERE Key_name = 'uq_users_email'")->fetch();
    if (!$emailIndex) {
        $pdo->exec("ALTER TABLE `users` ADD UNIQUE KEY `uq_users_email` (`email`)");
    }

    // Check if HR sample account exists, if not create one
    $chkHr = $pdo->query("SELECT COUNT(*) FROM `users` WHERE `emp_code` = 'HR001'")->fetchColumn();
    if ($chkHr == 0) {
        $hash = password_hash('hr123', PASSWORD_BCRYPT, ['cost' => 12]);
        $pdo->exec("INSERT INTO `users` (`emp_code`, `email`, `name`, `password_hash`, `role`, `category_id`, `basic_salary`, `yearly_vacation_days`)
                    VALUES ('HR001', 'hr001@example.test', 'مسؤول الموارد البشرية', '{$hash}', 'hr', 1, 11000.00, 25)");
    }

    echo "HR Role migration completed successfully!\n";
} catch (Exception $e) {
    echo "Migration error: " . $e->getMessage() . "\n";
}
