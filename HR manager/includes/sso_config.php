<?php
/** Read a PHP environment setting, with an optional local .env fallback. */
function heraSetting(string $key, string $default = ''): string
{
    $value = getenv($key);
    if ($value !== false && $value !== '') {
        return $value;
    }

    static $local = null;
    if ($local === null) {
        $local = [];
        $path = dirname(__DIR__) . '/.env';
        if (is_file($path) && is_readable($path)) {
            foreach (file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $line) {
                $line = trim($line);
                if ($line === '' || str_starts_with($line, '#') || !str_contains($line, '=')) {
                    continue;
                }
                [$name, $setting] = explode('=', $line, 2);
                $local[trim($name)] = trim(trim($setting), " \t\n\r\0\x0B\"'");
            }
        }
    }
    return (string)($local[$key] ?? $default);
}
