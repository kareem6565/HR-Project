<?php
/**
 * update_db_geofence.php — retired.
 *
 * The HR Manager schema is managed by Alembic (revision 020_hr_ops_schema)
 * inside the single HERA PostgreSQL database. This script no longer runs any
 * DDL and exists only to explain where the schema comes from now.
 */

http_response_code(410);
header('Content-Type: text/plain; charset=utf-8');
echo "This migration script has been retired.\n\n";
echo "The HR Manager tables now live in the hr_ops schema of the HERA PostgreSQL database.\n";
echo "Apply schema changes with Alembic:\n";
echo "  cd \"HR create jop/backend\"\n";
echo "  .venv\\Scripts\\python.exe -m alembic upgrade head\n";
