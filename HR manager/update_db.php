<?php
/**
 * update_db.php — Database migration script for categories, shifts, breaks, and cutoff limits.
 */
require_once __DIR__ . '/includes/db.php';

try {
    $pdo = getPDO();

    // 1. Create categories table if not exists
    $pdo->exec("CREATE TABLE IF NOT EXISTS `categories` (
      `id`                     INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      `name`                   VARCHAR(100) NOT NULL,
      `work_start_time`        TIME NOT NULL DEFAULT '09:00:00',
      `work_end_time`          TIME NOT NULL DEFAULT '18:00:00',
      `break_start_time`       TIME NOT NULL DEFAULT '13:00:00',
      `break_duration_minutes` INT UNSIGNED NOT NULL DEFAULT 60,
      `cutoff_minutes`         INT UNSIGNED NOT NULL DEFAULT 60,
      `center_latitude`        DECIMAL(10,7) NOT NULL DEFAULT 24.7136000,
      `center_longitude`       DECIMAL(10,7) NOT NULL DEFAULT 46.6753000,
      `allowed_radius_meters`  INT UNSIGNED NOT NULL DEFAULT 300,
      `created_at`             TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;");

    // Check if default category exists, if not create one
    $chkCat = $pdo->query("SELECT COUNT(*) FROM `categories`")->fetchColumn();
    if ($chkCat == 0) {
        $pdo->exec("INSERT INTO `categories` (`name`, `work_start_time`, `work_end_time`, `break_start_time`, `break_duration_minutes`, `cutoff_minutes`, `center_latitude`, `center_longitude`, `allowed_radius_meters`)
        VALUES ('الشفت الصباحي (الافتراضي)', '09:00:00', '18:00:00', '13:00:00', 60, 60, 24.7136000, 46.6753000, 300)");
    }

    $defaultCatId = $pdo->query("SELECT id FROM `categories` ORDER BY id ASC LIMIT 1")->fetchColumn();

    // 2. Add category_id to users if not exists
    $colsUsers = $pdo->query("SHOW COLUMNS FROM `users` LIKE 'category_id'")->fetch();
    if (!$colsUsers) {
        $pdo->exec("ALTER TABLE `users` ADD COLUMN `category_id` INT UNSIGNED NULL AFTER `role`");
        $pdo->exec("ALTER TABLE `users` ADD CONSTRAINT `fk_users_category` FOREIGN KEY (`category_id`) REFERENCES `categories`(`id`) ON DELETE SET NULL");
        // Assign default category to existing employees
        if ($defaultCatId) {
            $pdo->exec("UPDATE `users` SET `category_id` = {$defaultCatId} WHERE `role` = 'employee'");
        }
    }

    // 3. Add break columns to attendance if not exists
    $colsAttBreakIn = $pdo->query("SHOW COLUMNS FROM `attendance` LIKE 'break_start_time'")->fetch();
    if (!$colsAttBreakIn) {
        $pdo->exec("ALTER TABLE `attendance` ADD COLUMN `break_start_time` TIME NULL AFTER `check_out_time`");
        $pdo->exec("ALTER TABLE `attendance` ADD COLUMN `break_end_time` TIME NULL AFTER `break_start_time`");
    }

    echo "Database migration completed successfully!\n";
} catch (Exception $e) {
    echo "Migration error: " . $e->getMessage() . "\n";
}
