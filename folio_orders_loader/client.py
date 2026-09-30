"""Read a tenant .ini file and build a FolioClient."""
import ssl
from pathlib import Path


def read_ini(path):
    """Parse 'key = value' tenant files; comments and [sections] are ignored."""
    values = {}
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line[0] in ";#[" or "=" not in line:
            continue
        key, val = line.split("=", 1)
        values[key.strip()] = val.strip().strip('"').strip("'")
    return values


def ssl_setting(value):
    """sslVerify may be true/false or the path of a CA bundle."""
    if value is None or str(value).strip().lower() in ("", "true", "1", "yes"):
        return True
    if str(value).strip().lower() in ("false", "0", "no"):
        return False
    if Path(value).exists():
        return ssl.create_default_context(cafile=value)
    return True


def connect(ini_path):
    """Return a FolioClient for the tenant described by ini_path."""
    from folioclient import FolioClient
    ini = read_ini(ini_path)
    missing = [k for k in ("okapiUrl", "tenant_id", "username", "password")
               if not ini.get(k)]
    if missing:
        raise ValueError("%s is missing: %s" % (ini_path, ", ".join(missing)))
    return FolioClient(ini["okapiUrl"], ini["tenant_id"], ini["username"],
                       ini["password"], ssl_verify=ssl_setting(ini.get("sslVerify")))
