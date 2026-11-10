<?php
/**
 * Database connection — PDO singleton backed by PostgreSQL.
 *
 * The HR Manager tables live in the `hr_ops` schema of the single HERA
 * PostgreSQL database. Every value can be overridden with an environment
 * variable (DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS, DB_SCHEMA) or with
 * an optional includes/db.local.php that defines the same constants.
 */

function hrDbEnv(string $key, string $default): string
{
    $value = getenv($key);
    if ($value === false || $value === '') {
        $value = $_SERVER[$key] ?? $_ENV[$key] ?? '';
    }
    return ($value === false || $value === '') ? $default : (string)$value;
}

if (file_exists(__DIR__ . '/db.local.php')) {
    require_once __DIR__ . '/db.local.php';
}

defined('DB_HOST')   || define('DB_HOST', hrDbEnv('DB_HOST', '127.0.0.1'));
defined('DB_PORT')   || define('DB_PORT', hrDbEnv('DB_PORT', '5432'));
defined('DB_NAME')   || define('DB_NAME', hrDbEnv('DB_NAME', 'hr_ai_assistant'));
defined('DB_USER')   || define('DB_USER', hrDbEnv('DB_USER', 'hr_ai_assistant'));
defined('DB_PASS')   || define('DB_PASS', hrDbEnv('DB_PASS', 'hr_ai_assistant'));
defined('DB_SCHEMA') || define('DB_SCHEMA', hrDbEnv('DB_SCHEMA', 'hr_ops'));

function hrDbQuotedSchema(): string
{
    return '"' . str_replace('"', '""', DB_SCHEMA) . '"';
}

function getPDO(bool $throwOnFailure = false): PDO
{
    static $pdo = null;

    if ($pdo === null) {
        $dsn = sprintf(
            'pgsql:host=%s;port=%s;dbname=%s',
            DB_HOST,
            DB_PORT,
            DB_NAME
        );

        $options = [
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES   => false,
        ];

        try {
            $connection = new PDO($dsn, DB_USER, DB_PASS, $options);
            $connection->exec('SET search_path TO ' . hrDbQuotedSchema() . ', public');
            $pdo = $connection;
        } catch (PDOException $e) {
            error_log('HR Manager database connection failed: ' . $e->getMessage());
            if ($throwOnFailure) {
                throw new RuntimeException('Database connection failed.', 0, $e);
            }
            // Never expose raw errors in production
            http_response_code(500);
            die(json_encode(['success' => false, 'message' => 'Database connection failed.']));
        }
    }

    return $pdo;
}
