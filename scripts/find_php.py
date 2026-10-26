"""Find a PHP that can run the hosted layer's checks, and build its command line.

The tracker's PHP layer (php/, includes/, tools/*.php) is not deployed on this
computer, so its checks need a PHP from somewhere. Search order, first hit wins:

  1. $PRI_PHP, the full path to php.exe (or php)
  2. tools/php/php.exe beside the app (git-ignored; a portable copy per machine)
  3. php on the PATH

PHP is started with -n (no php.ini) and the PDO drivers loaded explicitly from the
ext folder beside the binary, so a php.ini on the machine cannot change what runs.
Nothing is downloaded or installed.

    py scripts/find_php.py          # prints where PHP was found and its version
"""
import os, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTENSIONS = ["pdo_pgsql", "pdo_sqlite", "mbstring"]


def find():
    """The path to a PHP binary, or None. Never raises."""
    env = os.environ.get("PRI_PHP", "").strip()
    if env and os.path.isfile(env):
        return env
    for name in ("php.exe", "php"):
        p = os.path.join(ROOT, "tools", "php", name)
        if os.path.isfile(p):
            return p
    return shutil.which("php")


def command(php=None):
    """The argument list that starts PHP with the PDO drivers the layer needs.

    With a portable PHP (an ext folder beside the binary) the drivers are loaded
    by name; a PHP from the PATH keeps its own configuration, because its
    extensions live wherever its packager put them.
    """
    php = php or find()
    if not php:
        return None
    ext = os.path.join(os.path.dirname(php), "ext")
    if not os.path.isdir(ext):
        return [php]
    args = [php, "-n", "-d", "extension_dir=" + ext]
    for name in EXTENSIONS:
        if os.path.isfile(os.path.join(ext, "php_%s.dll" % name)) or \
           os.path.isfile(os.path.join(ext, "%s.so" % name)):
            args += ["-d", "extension=" + name]
    return args


def main():
    cmd = command()
    if not cmd:
        print("PHP not found. Looked at $PRI_PHP, %s and the PATH."
              % os.path.join(ROOT, "tools", "php", "php.exe"))
        return 1
    r = subprocess.run(cmd + ["-r", "echo PHP_VERSION, ' ', implode(',', array_filter(PDO::getAvailableDrivers())), PHP_EOL;"],
                       capture_output=True, text=True)
    print("php     %s" % cmd[0])
    print("version %s" % (r.stdout.strip() or r.stderr.strip()))
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
