<?php
/**
 * update_db_work.php — Migration script for work_submissions table and upload directory.
 */
require_once __DIR__ . '/includes/db.php';

try {
    $pdo = getPDO();

    // 1. Create work_submissions table
    $pdo->exec("CREATE TABLE IF NOT EXISTS `work_submissions` (
      `id`               INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      `user_id`          INT UNSIGNED NOT NULL,
      `title`            VARCHAR(255) NOT NULL,
      `description`      TEXT NULL,
      `submission_type`  ENUM('pdf', 'image', 'text', 'link') NOT NULL DEFAULT 'text',
      `file_path`        VARCHAR(255) NULL,
      `external_link`    VARCHAR(255) NULL,
      `status`           ENUM('in_progress', 'completed', 'pending_review') NOT NULL DEFAULT 'completed',
      `admin_status`     ENUM('pending', 'approved', 'needs_revision') NOT NULL DEFAULT 'pending',
      `admin_feedback`   TEXT NULL,
      `submitted_at`     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      CONSTRAINT `fk_work_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;");

    // 2. Create uploads/work directory if not exists
    $uploadDir = __DIR__ . '/uploads/work';
    if (!file_exists($uploadDir)) {
        mkdir($uploadDir, 0777, true);
    }

    echo "Work submissions table and upload directory created successfully!\n";
} catch (Exception $e) {
    echo "Migration error: " . $e->getMessage() . "\n";
}
