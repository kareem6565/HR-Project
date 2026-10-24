<?php
/**
 * One-time migration for live geofence tracking and break overrun records.
 */
require_once __DIR__ . '/includes/db.php';

function geofenceColumnExists(PDO $pdo, string $column): bool
{
    return (bool)$pdo->query("SHOW COLUMNS FROM `attendance` LIKE " . $pdo->quote($column))->fetch();
}

function addGeofenceColumn(PDO $pdo, string $column, string $definition): void
{
    if (!geofenceColumnExists($pdo, $column)) {
        $pdo->exec("ALTER TABLE `attendance` ADD COLUMN `{$column}` {$definition}");
    }
}

try {
    $pdo = getPDO();
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

    addGeofenceColumn($pdo, 'lat_out', 'DECIMAL(10,7) NULL AFTER `lat_in`');
    addGeofenceColumn($pdo, 'lng_out', 'DECIMAL(10,7) NULL AFTER `lng_in`');
    addGeofenceColumn($pdo, 'distance_out_meters', 'INT NULL AFTER `distance_in_meters`');
    addGeofenceColumn($pdo, 'last_lat', 'DECIMAL(10,7) NULL AFTER `lng_out`');
    addGeofenceColumn($pdo, 'last_lng', 'DECIMAL(10,7) NULL AFTER `last_lat`');
    addGeofenceColumn($pdo, 'last_location_at', 'DATETIME NULL AFTER `last_lng`');
    addGeofenceColumn($pdo, 'geofence_status', "ENUM('inside','outside','unknown') NOT NULL DEFAULT 'unknown' AFTER `last_location_at`");
    addGeofenceColumn($pdo, 'break_overrun_minutes', 'INT UNSIGNED NOT NULL DEFAULT 0 AFTER `break_end_time`');

    $pdo->exec("CREATE TABLE IF NOT EXISTS `geofence_events` (
        `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        `user_id` INT UNSIGNED NOT NULL,
        `attendance_id` INT UNSIGNED NULL,
        `event_type` VARCHAR(40) NOT NULL,
        `lat` DECIMAL(10,7) NULL,
        `lng` DECIMAL(10,7) NULL,
        `distance_meters` INT NULL,
        `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        INDEX `idx_geofence_user_created` (`user_id`, `created_at`),
        INDEX `idx_geofence_attendance` (`attendance_id`),
        CONSTRAINT `fk_geofence_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
        CONSTRAINT `fk_geofence_attendance` FOREIGN KEY (`attendance_id`) REFERENCES `attendance` (`id`) ON DELETE SET NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");

    echo "Geofence migration completed successfully.\n";
} catch (Throwable $e) {
    http_response_code(500);
    echo 'Migration error: ' . $e->getMessage() . "\n";
}
