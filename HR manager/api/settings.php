<?php
/**
 * api/settings.php
 *
 * GET  → return current company settings
 * POST → update company settings (admin / HR) & sync with category locations
 */

require_once __DIR__ . '/../includes/db.php';
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/helpers.php';

header('Content-Type: application/json; charset=utf-8');

requireHR();

$pdo    = getPDO();
$method = $_SERVER['REQUEST_METHOD'];

if ($method === 'GET') {
    jsonResponse(true, 'OK', ['settings' => getCompanySettings($pdo)]);
}

if ($method === 'POST') {
    $body = json_decode(file_get_contents('php://input'), true);

    $required = ['company_name', 'center_latitude', 'center_longitude', 'allowed_radius_meters'];
    foreach ($required as $field) {
        if (!isset($body[$field]) || $body[$field] === '') {
            jsonResponse(false, "الحقل '{$field}' مطلوب.");
        }
    }

    $lat    = (float)$body['center_latitude'];
    $lng    = (float)$body['center_longitude'];
    $radius = (int)$body['allowed_radius_meters'];
    $name   = trim($body['company_name']);

    if ($name === '') {
        jsonResponse(false, 'اسم الشركة مطلوب.');
    }
    if (!isValidGeoPoint($lat, $lng)) {
        jsonResponse(false, 'إحداثيات موقع الشركة غير صحيحة.');
    }
    if ($radius < 25 || $radius > 10000) {
        jsonResponse(false, 'نطاق الشركة يجب أن يكون بين 25 و10,000 متر.');
    }

    $settings = getCompanySettings($pdo);

    // 1. Update company_settings table
    $stmt = $pdo->prepare(
        "UPDATE company_settings
         SET company_name=?, center_latitude=?, center_longitude=?, allowed_radius_meters=?
         WHERE id=?"
    );
    $stmt->execute([$name, $lat, $lng, $radius, $settings['id']]);

    // 2. Also update all categories to use the new company center location & radius!
    $pdo->prepare(
        "UPDATE categories
         SET center_latitude = ?, center_longitude = ?, allowed_radius_meters = ?"
    )->execute([$lat, $lng, $radius]);

    jsonResponse(true, 'تم حفظ إعدادات الشركة وتحديث كافة النطاقات الجغرافية للفئات بنجاح.');
}

jsonResponse(false, 'Method not allowed.');
