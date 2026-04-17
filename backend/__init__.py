import sys
from pathlib import Path
import importlib

package_dir = Path(__file__).resolve().parent
package_path = str(package_dir)
if package_path not in sys.path:
    sys.path.insert(0, package_path)


def _alias(name: str) -> None:
    module = importlib.import_module(f"backend.{name}")
    sys.modules.setdefault(name, module)


for module_name in [
    "config",
    "database",
    "dependencies",
    "bootstrap",
    "contracts",
    "domain",
    "modules",
    "routes",
    "services",
    "workers",
]:
    try:
        _alias(module_name)
    except Exception:
        continue
