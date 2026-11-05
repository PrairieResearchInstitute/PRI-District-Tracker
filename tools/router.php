<?php
// Router for the PHP built-in server that tools/serve.ps1 starts:
//
//     php -S 127.0.0.1:<port> -t "<app folder>" "<app folder>\tools\router.php"
//
// The app folder is the document root, as in the container (Dockerfile:
// APACHE_DOCUMENT_ROOT is the copied app folder), so index.html is the main page,
// health.php the health check and php/data.php, php/admin_ingest.php the PHP routes.
// The container's Apache refuses includes, tools, migrations, sql and templates;
// this router refuses the same folders, plus what sits in the working folder but
// never ships in the image (.dockerignore): reference, scripts, tests, backups,
// dot folders, the settings files and the database of record.
//
// Windows resolves "includes." and "includes " to "includes" and an 8.3 short name
// to its long name, so trailing dots and spaces are ignored and any segment with a
// tilde is refused.
$path = rawurldecode((string) parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH));
$path = str_replace('\\', '/', $path);
$segments = array_values(array_filter(explode('/', $path), 'strlen'));
$internal = ['includes', 'tools', 'migrations', 'sql', 'templates',
             'reference', 'scripts', 'tests', 'backups'];
$files = ['config.local.json', 'config.template.json', 'activities.json'];

foreach ($segments as $i => $raw) {
    $seg = strtolower(rtrim($raw, '. '));
    if ($seg === '' || $seg[0] === '.' || strpos($seg, '~') !== false
        || ($i === 0 && in_array($seg, $internal, true))
        || in_array($seg, $files, true) || preg_match('/\.env$/', $seg)) {
        http_response_code(403);
        header('Content-Type: text/plain; charset=utf-8');
        echo "Forbidden\n";
        return true;
    }
}
return false;   // the built-in server serves the file or runs the .php script
