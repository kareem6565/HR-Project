<?php
/**
 * update_db_hr.php — Migration script for HR role support.
 */
require_once __DIR__ . '/includes/db.php';

try {
    $pdo = getPDO();

    // Update role ENUM in users table to include 'hr'
    $pdo->exec("ALTER TABLE `users` MODIFY COLUMN `role` ENUM('admin', 'hr', 'employee') NOT NULL DEFAULT 'employee'");

    // Check if HR sample account exists, if not create one
    $chkHr = $pdo->query("SELECT COUNT(*) FROM `users` WHERE `emp_code` = 'HR001'")->fetchColumn();
    if ($chkHr == 0) {
        $hash = password_hash('hr123', PASSWORD_BCRYPT, ['cost' => 12]);
        $pdo->exec("INSERT INTO `users` (`emp_code`, `name`, `password_hash`, `role`, `category_id`, `basic_salary`, `yearly_vacation_days`)
                    VALUES ('HR001', 'مسؤول الموارد البشرية', '{$hash}', 'hr', 1, 11000.00, 25)");
    }

    echo "HR Role migration completed successfully!\n";
} catch (Exception $e) {
    echo "Migration error: " . $e->getMessage() . "\n";
}
