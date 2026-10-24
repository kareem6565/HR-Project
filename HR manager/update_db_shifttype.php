<?php
/**
 * update_db_shifttype.php — Migration to add shift_type column to categories.
 */
require_once __DIR__ . '/includes/db.php';

try {
    $pdo = getPDO();

    $cols = $pdo->query("SHOW COLUMNS FROM `categories` LIKE 'shift_type'")->fetch();
    if (!$cols) {
        $pdo->exec("ALTER TABLE `categories` ADD COLUMN `shift_type` ENUM('day', 'night') NOT NULL DEFAULT 'day' AFTER `name`");
    }

    // Auto-set existing night shifts
    $pdo->exec("UPDATE `categories` SET `shift_type` = 'night' WHERE `work_end_time` < `work_start_time` OR `work_start_time` >= '16:00:00' OR `work_start_time` = '00:00:00'");

    echo "Shift type migration completed successfully!\n";
} catch (Exception $e) {
    echo "Migration error: " . $e->getMessage() . "\n";
}
