<?php
require_once __DIR__ . '/includes/auth.php';
require_once __DIR__ . '/includes/sso_config.php';

requireLogin();
if (($_SESSION['role'] ?? '') !== 'hr') {
    http_response_code(403);
    exit('HR access is required.');
}

$secret = heraSetting('HERA_SSO_SHARED_SECRET');
$frontend = heraSetting('HERA_FRONTEND_URL', 'http://localhost:5173');
$issuer = heraSetting('HERA_SSO_ISSUER', 'hr-manager');
$parts = parse_url($frontend);
if (strlen($secret) < 32 || !is_array($parts) || !in_array($parts['scheme'] ?? '', ['http', 'https'], true) || empty($parts['host'])) {
    http_response_code(503);
    exit('Single sign-on is not configured. Set HERA_SSO_SHARED_SECRET and HERA_FRONTEND_URL in the PHP environment.');
}

$encode = static fn(string $value): string => rtrim(strtr(base64_encode($value), '+/', '-_'), '=');
$header = $encode(json_encode(['alg' => 'HS256', 'typ' => 'JWT'], JSON_THROW_ON_ERROR));
$payload = $encode(json_encode([
    'iss' => $issuer,
    'aud' => 'hera-recruitment',
    'sub' => (string)($_SESSION['emp_code'] ?? ''),
    'name' => (string)($_SESSION['name'] ?? ''),
    'role' => 'hr',
    'iat' => time(),
    'exp' => time() + 45,
], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR));
$unsigned = $header . '.' . $payload;
$signature = $encode(hash_hmac('sha256', $unsigned, $secret, true));
$assertion = $unsigned . '.' . $signature;
$target = rtrim($frontend, '/') . '/sso/callback#assertion=' . rawurlencode($assertion);
header('Cache-Control: no-store, private');
header('Referrer-Policy: no-referrer');
header('Location: ' . $target, true, 303);
exit;
