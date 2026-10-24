<?php
/**
 * Retired work-submissions endpoint.
 * Existing submission records and uploaded files are retained for data preservation.
 */
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/helpers.php';
header('Content-Type: application/json; charset=utf-8');
requireLogin();
http_response_code(410);
jsonResponse(false, 'ميزة إنجازاتي وخط سير العمل غير متاحة.');
