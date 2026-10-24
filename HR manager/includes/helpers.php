<?php
// Set default timezone (Cairo / Egypt / Saudi timezone UTC+3)
date_default_timezone_set('Africa/Cairo');


/**
 * Send a JSON response and terminate execution.
 */
function jsonResponse(bool $success, string $message, array $data = []): never
{
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode(array_merge(['success' => $success, 'message' => $message], $data));
    exit;
}

/**
 * Haversine formula — distance between two GPS coordinates (in meters).
 */
function haversineDistance(float $lat1, float $lng1, float $lat2, float $lng2): float
{
    $earthRadiusM = 6371000;

    $dLat = deg2rad($lat2 - $lat1);
    $dLng = deg2rad($lng2 - $lng1);

    $a = sin($dLat / 2) ** 2
       + cos(deg2rad($lat1)) * cos(deg2rad($lat2)) * sin($dLng / 2) ** 2;

    return $earthRadiusM * 2 * atan2(sqrt($a), sqrt(1 - $a));
}

/**
 * Sanitise a string input.
 */
function clean(string $input): string
{
    return htmlspecialchars(trim($input), ENT_QUOTES, 'UTF-8');
}

/**
 * Validate coordinates received from browser geolocation before using them.
 */
function isValidGeoPoint(mixed $lat, mixed $lng): bool
{
    if (!is_numeric($lat) || !is_numeric($lng)) return false;
    $latitude = (float)$lat;
    $longitude = (float)$lng;
    return is_finite($latitude) && is_finite($longitude)
        && $latitude >= -90 && $latitude <= 90
        && $longitude >= -180 && $longitude <= 180;
}

/**
 * Build the real start/end timestamps for a day or cross-midnight shift.
 * The supplied shift date is the date on which the shift started.
 */
function getShiftWindow(string $shiftDate, string $workStart, string $workEnd): array
{
    $start = new DateTime("{$shiftDate} {$workStart}");
    $end   = new DateTime("{$shiftDate} {$workEnd}");
    if ($end <= $start) $end->modify('+1 day');
    return ['start' => $start, 'end' => $end];
}

/**
 * Resolve a scheduled time within a shift, including shifts that cross midnight.
 */
function getShiftScheduledTime(string $shiftDate, string $workStart, string $workEnd, string $scheduledTime): DateTime
{
    $time = new DateTime("{$shiftDate} {$scheduledTime}");
    $window = getShiftWindow($shiftDate, $workStart, $workEnd);
    if ($window['end']->format('Y-m-d') !== $window['start']->format('Y-m-d') && $time < $window['start']) {
        $time->modify('+1 day');
    }
    return $time;
}

/**
 * Fetch the single company settings row (creates default if missing).
 */
function getCompanySettings(\PDO $pdo): array
{
    $row = $pdo->query('SELECT * FROM company_settings LIMIT 1')->fetch();
    if (!$row) {
        $pdo->exec("INSERT INTO company_settings (company_name) VALUES ('My Company')");
        $row = $pdo->query('SELECT * FROM company_settings LIMIT 1')->fetch();
    }
    return $row;
}

/**
 * Fetch full category details for a user.
 */
function getUserCategory(\PDO $pdo, int $userId): array
{
    $stmt = $pdo->prepare(
        "SELECT c.*, c.name AS category_name, c.center_latitude AS cat_lat, c.center_longitude AS cat_lng, c.allowed_radius_meters AS cat_radius
         FROM users u
         LEFT JOIN categories c ON c.id = u.category_id
         WHERE u.id = ?"
    );
    $stmt->execute([$userId]);
    $cat = $stmt->fetch();

    if ($cat && !empty($cat['id'])) {
        return $cat;
    }

    // Fallback to company_settings
    $settings = getCompanySettings($pdo);
    return [
        'id'                     => null,
        'name'                   => 'عام',
        'category_name'          => 'عام',
        'work_start_time'        => '09:00:00',
        'work_end_time'          => '18:00:00',
        'break_start_time'       => '13:00:00',
        'break_duration_minutes' => 60,
        'cutoff_minutes'         => 60,
        'center_latitude'        => (float)$settings['center_latitude'],
        'center_longitude'       => (float)$settings['center_longitude'],
        'allowed_radius_meters'  => (int)$settings['allowed_radius_meters'],
        'cat_lat'                => (float)$settings['center_latitude'],
        'cat_lng'                => (float)$settings['center_longitude'],
        'cat_radius'             => (int)$settings['allowed_radius_meters'],
    ];
}
