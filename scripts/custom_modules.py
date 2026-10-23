"""Nombres técnicos de los módulos bajo addons-incoespacio."""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "addons-incoespacio"))


def custom_modules(root=None):
    root = root or ROOT
    names = []
    for dp, _dns, fns in os.walk(root):
        if "__manifest__.py" in fns:
            names.append(os.path.basename(dp))
    return sorted(names)


if __name__ == "__main__":
    mods = custom_modules()
    if "--tags" in sys.argv:
        # Solo los tests de estos modulos. Sin esto, --test-enable lanza tambien
        # los de account/base, que en una base vacia no son el resultado nuestro.
        print(",".join("/" + name for name in mods))
    elif "--csv" in sys.argv:
        print(",".join(mods))
    else:
        print("\n".join(mods))
