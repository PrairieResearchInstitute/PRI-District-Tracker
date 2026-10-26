"""The Studio: this application's own code, editable from inside it.

Borrowed, deliberately, from the Studio in PRI Facilities Request. It exists for the
day something is wrong and the person who can open a code editor is not available. It
is powerful - it writes the scripts the next build runs - so every part of it assumes
the person using it is tired, in a hurry, and about to make a mistake:

    confined    a path is RESOLVED and then checked to be inside the project folder.
                Not string-matched - resolved - so "..", a symlink, or a Windows short
                name cannot walk out of it.
    checked     the file is parsed before it is written. Python that would not import,
                or JSON that would not load, is refused rather than saved.
    reversible  every save copies the old file aside first, so any change goes back
                with one click and no typing.
    recorded    who saved what, when, and how much it changed.

The Data Console that serves this binds to 127.0.0.1, so the gate is the machine
itself. If this is ever exposed beyond localhost it needs its own access grant, the
way Facilities grants 'studio' separately from being an administrator.

Pure stdlib.
"""
import os, json, shutil, datetime, getpass

import app_config

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Files the Studio will open. Anything else is data, not code.
EXTENSIONS = {"py", "php", "js", "css", "html", "htm", "json", "sql", "md",
              "yaml", "yml", "txt", "bat", "ps1", "ini", "csv"}

# Never listed: version control, caches, the backups this feature writes, the
# git-ignored reference folder, and the
# vendored offline bundle (generated, and large enough to make the tree useless).
SKIP_DIRS = {".git", "__pycache__", "node_modules", "backups", "venv", ".venv", "reference",
             ".tmp"}
# tools/php is a portable PHP copied per machine (git-ignored); migrations/ are frozen
# once applied anywhere (tools/migrate.php refuses a changed file), so a fix is a new
# numbered file written in an editor with the tests watching, never an edit here.
SKIP_REL_DIRS = {"assets/vendor", "tools/php", "migrations"}

# Per-machine settings: only scripts/app_config.py writes config.local.json.
PRIVATE = {"config.local.json"}

# Build outputs. Editing them is pointless - the next build overwrites the lot.
# includes/core.php is a drez-php-core copy: fix it in the library and pull again.
GENERATED = {"index.html", "handout.html", "PRI-Tracker-Kit.html", "data.js",
             "data/geo.json", "data/reps.json", "sql/data.sql",
             "includes/core.php"}

# Larger than any source file here; keeps the big geodata out of the editor.
MAX_BYTES = 1048576


def _slash(p):
    return p.replace("\\", "/")


def backup_dir():
    d = os.path.join(app_config.backups_dir(), "studio")
    os.makedirs(d, exist_ok=True)
    return d


def resolve(rel):
    """Turn a path from the browser into a real file inside the project, or nothing.

    The check is on the RESOLVED path, because comparing the string the browser sent
    would be fooled by "..", by a symlink, and on Windows by an 8.3 short name.
    """
    if not rel or "\0" in rel:
        return None
    root = _slash(os.path.realpath(ROOT))
    full = _slash(os.path.realpath(os.path.join(ROOT, rel.strip().lstrip("/\\"))))
    if full != root and not full.startswith(root + "/"):
        return None
    if not os.path.isfile(full):
        return None
    if os.path.splitext(full)[1].lstrip(".").lower() not in EXTENSIONS:
        return None
    # Whatever the tree declines to list, this declines to open. The two must agree, or
    # a file is hidden from the editor yet still writable by typing its path.
    rel_path = _slash(os.path.relpath(full, root))
    # A build output: editing one is silently undone by the next build.
    if rel_path in GENERATED | PRIVATE:
        return None
    # Inside a folder the tree skips: version control, caches, reference material, and
    # the backups, which are the copies a restore reads back.
    folders = rel_path.split("/")[:-1]
    if any(f in SKIP_DIRS for f in folders):
        return None
    if any(rel_path.startswith(s + "/") for s in SKIP_REL_DIRS):
        return None
    # Too big for the tree to list is too big to write back: a save would otherwise
    # replace a file the editor was never able to show.
    try:
        if os.path.getsize(full) > MAX_BYTES:
            return None
    except OSError:
        return None
    return full


def relative(full):
    return _slash(os.path.relpath(full, ROOT))


def tree():
    """Every file the Studio is willing to open, alphabetical, because people look
    for a name."""
    out = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        rel_dir = _slash(os.path.relpath(dirpath, ROOT))
        if rel_dir == ".":
            rel_dir = ""
        if any(rel_dir == s or rel_dir.startswith(s + "/") for s in SKIP_REL_DIRS):
            dirnames[:] = []
            continue
        for fn in sorted(filenames):
            rel = (rel_dir + "/" + fn) if rel_dir else fn
            if rel in GENERATED or rel in PRIVATE:
                continue
            if os.path.splitext(fn)[1].lstrip(".").lower() not in EXTENSIONS:
                continue
            full = os.path.join(dirpath, fn)
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            if size > MAX_BYTES:
                continue
            out.append({"path": rel, "size": size,
                        "dir": rel_dir or "(root)",
                        "writable": os.access(full, os.W_OK)})
    return out


def check(rel, code):
    """Parse before writing. Nothing here executes the code being checked."""
    ext = os.path.splitext(rel)[1].lstrip(".").lower()
    if ext == "py":
        try:
            compile(code, rel, "exec")          # parses only; does not run
            return True, "Python parses."
        except SyntaxError as e:
            return False, "Python syntax error on line %s: %s" % (e.lineno, e.msg)
    if ext == "json":
        try:
            json.loads(code)
            return True, "JSON is valid."
        except ValueError as e:
            return False, "JSON error: %s" % e
    if ext == "php":
        # PHP cannot be parsed from Python. Catch the mistake that actually happens -
        # an unbalanced block - and say plainly that this is not a full parse.
        if "<?php" not in code:
            return False, "That does not look like a PHP file (no opening tag)."
        for open_c, close_c, what in (("{", "}", "braces"), ("(", ")", "parentheses")):
            if code.count(open_c) != code.count(close_c):
                return False, ("Unbalanced %s (%d open, %d close). Nothing was written."
                               % (what, code.count(open_c), code.count(close_c)))
        return True, "Balanced, but PHP is not fully parsed here - test it on the server."
    return True, "Not a parsed type, so saved as written."


def backup_name(rel):
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "__" + rel.replace("/", "~")


def backups(rel):
    """Every kept copy of one file, newest first."""
    suffix = "__" + rel.replace("/", "~")
    out = []
    for e in os.listdir(backup_dir()):
        if e.endswith(suffix):
            p = os.path.join(backup_dir(), e)
            out.append({"name": e, "when": e[:15], "size": os.path.getsize(p)})
    out.sort(key=lambda r: r["name"], reverse=True)
    return out


def log(action, rel, detail=""):
    """A change to the code is worth a record."""
    line = json.dumps({"at": datetime.datetime.now().isoformat(timespec="seconds"),
                       "who": getpass.getuser(), "action": action,
                       "file": rel, "detail": detail}) + "\n"
    with open(os.path.join(backup_dir(), "history.log"), "a", encoding="utf-8") as f:
        f.write(line)


def history(limit=60):
    p = os.path.join(backup_dir(), "history.log")
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        lines = f.readlines()[-limit:]
    out = []
    for ln in reversed(lines):
        try:
            out.append(json.loads(ln))
        except ValueError:
            pass
    return out


def read(rel):
    full = resolve(rel)
    if full is None:
        return False, "That file is not part of this application."
    if os.path.getsize(full) > MAX_BYTES:
        return False, "That file is too large to edit here."
    with open(full, encoding="utf-8", errors="replace") as f:
        return True, f.read()


def save(rel, code):
    """Check it, keep the old one, then write.

    Nothing is written unless the check passes, so a syntax error costs a message
    rather than the next build.
    """
    full = resolve(rel)
    if full is None:
        return False, "That file is not part of this application."
    if not os.access(full, os.W_OK):
        return False, "The file is read-only on disk."

    code = code.replace("\r\n", "\n")   # a textarea sends CRLF; storing it rewrites every line
    ok, msg = check(rel, code)
    if not ok:
        log("refused", rel, msg)
        return False, msg + " Nothing was written."

    with open(full, encoding="utf-8", errors="replace") as f:
        before = f.read()
    if before == code:
        return True, "No change to save."

    try:
        shutil.copy2(full, os.path.join(backup_dir(), backup_name(rel)))
    except OSError as e:
        return False, "Could not keep a copy of the old file, so nothing was written (%s)." % e

    # Written whole and then moved into place, so a half-written file never exists
    # for the next build to import.
    tmp = full + ".studio-tmp"
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(code)
        os.replace(tmp, full)
    except OSError as e:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False, "The write failed. The file is unchanged (%s)." % e

    delta = len(code) - len(before)
    log("saved", rel, ("+" if delta >= 0 else "") + str(delta) + " bytes")
    return True, "Saved. %s The previous copy is kept." % msg


def restore(rel, name):
    """Put a kept copy back, keeping the current one first."""
    if os.path.basename(name) != name:
        return False, "Not a backup this Studio wrote."
    # The backup name ends with the path it was taken from. Without this check a copy
    # of one file could be written over a different file, quietly destroying it.
    if not name.endswith("__" + rel.replace("/", "~")):
        return False, "That copy belongs to a different file."
    src = os.path.join(backup_dir(), name)
    if not os.path.isfile(src):
        return False, "That copy is no longer there."
    with open(src, encoding="utf-8", errors="replace") as f:
        ok, msg = save(rel, f.read())
    if ok:
        log("restored", rel, name)
        return True, "Restored the copy from %s." % name[:15]
    return False, msg
