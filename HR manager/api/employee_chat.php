<?php
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/sso_config.php';

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, private');
requireLogin();

$actor = getCurrentUser();
if (($actor['role'] ?? '') !== 'employee') {
    http_response_code(403);
    echo json_encode(['message' => 'الخدمة متاحة لحسابات الموظفين فقط.'], JSON_UNESCAPED_UNICODE);
    exit;
}
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    header('Allow: POST');
    echo json_encode(['message' => 'طريقة الطلب غير مدعومة.'], JSON_UNESCAPED_UNICODE);
    exit;
}

$body = json_decode(file_get_contents('php://input'), true);
if (!is_array($body)) {
    http_response_code(400);
    echo json_encode(['message' => 'صيغة الرسالة غير صحيحة.'], JSON_UNESCAPED_UNICODE);
    exit;
}
$csrf = (string)($body['csrf'] ?? '');
if (empty($_SESSION['employee_chat_csrf']) || !hash_equals($_SESSION['employee_chat_csrf'], $csrf)) {
    http_response_code(403);
    echo json_encode(['message' => 'انتهت صلاحية الجلسة. حدّث الصفحة وحاول مرة أخرى.'], JSON_UNESCAPED_UNICODE);
    exit;
}
$message = trim((string)($body['message'] ?? ''));
$history = $body['history'] ?? [];
if ($message === '' || mb_strlen($message) > 2000 || !is_array($history)) {
    http_response_code(422);
    echo json_encode(['message' => 'اكتب رسالة لا تتجاوز 2000 حرف.'], JSON_UNESCAPED_UNICODE);
    exit;
}

$secret = heraSetting('HERA_SSO_SHARED_SECRET');
$issuer = heraSetting('HERA_SSO_ISSUER', 'hr-manager');
if (strlen($secret) < 32) {
    http_response_code(503);
    echo json_encode(['message' => 'تسجيل الدخول الآمن للمساعد غير مهيأ.'], JSON_UNESCAPED_UNICODE);
    exit;
}

$encode = static fn(string $value): string => rtrim(strtr(base64_encode($value), '+/', '-_'), '=');
$header = $encode(json_encode(['alg' => 'HS256', 'typ' => 'JWT'], JSON_THROW_ON_ERROR));
$payload = $encode(json_encode([
    'iss' => $issuer,
    'aud' => 'hera-employee-chat',
    'sub' => (string)($actor['emp_code'] ?? ''),
    'name' => (string)($actor['name'] ?? ''),
    'role' => 'employee',
    'iat' => time(),
    'exp' => time() + 45,
], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR));
$unsigned = $header . '.' . $payload;
$assertion = $unsigned . '.' . $encode(hash_hmac('sha256', $unsigned, $secret, true));

$apiBase = rtrim(heraSetting('HERA_API_BASE_URL', 'http://host.docker.internal:8000/api/v1'), '/');
$requestBody = json_encode([
    'message' => $message,
    'history' => array_slice($history, -8),
], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
$context = stream_context_create([
    'http' => [
        'method' => 'POST',
        'header' => "Content-Type: application/json\r\nX-HR-Employee-Assertion: {$assertion}\r\n",
        'content' => $requestBody,
        'timeout' => 60,
        'ignore_errors' => true,
    ],
]);
$upstream = @file_get_contents($apiBase . '/employee-chat/message', false, $context);
$statusLine = $http_response_header[0] ?? '';
preg_match('/\s([1-5][0-9]{2})\s/', $statusLine, $matches);
$upstreamStatus = isset($matches[1]) ? (int)$matches[1] : 0;
if (!is_string($upstream) || $upstreamStatus < 200 || $upstreamStatus >= 300) {
    http_response_code($upstreamStatus >= 400 ? $upstreamStatus : 503);
    $message = match ($upstreamStatus) {
        402 => 'رصيد أو حد الإنفاق لمزوّد الذكاء الاصطناعي غير كافٍ. راجع إعدادات الرصيد وحد الإنفاق في OpenRouter.',
        429 => 'حصة مزوّد الذكاء الاصطناعي لهذا النموذج غير متاحة حاليًا. تواصل مع مسؤول النظام أو جرّب لاحقًا.',
        503 => 'خدمة المساعد الذكي غير متاحة مؤقتًا. حاول مرة أخرى بعد قليل.',
        default => 'المساعد غير متاح الآن. حاول مرة أخرى بعد قليل.',
    };
    echo json_encode(['message' => $message], JSON_UNESCAPED_UNICODE);
    exit;
}

echo $upstream;
