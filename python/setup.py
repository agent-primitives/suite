"""Build-only copying from the owning schema tree; never runtime downloads."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.sdist import sdist

HERE = Path(__file__).resolve().parent


def bundle():
    retained = HERE / "_schema_source"
    if retained.is_dir():
        provenance = json.loads((retained / "provenance.json").read_bytes())
        source = retained
    else:
        source = HERE.parent / "schema"
        if subprocess.check_output(
            ["git", "status", "--porcelain", "--", "schema"], cwd=HERE.parent, text=True
        ).strip():
            raise ValueError("cannot bind schema provenance to a dirty schema tree")
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=HERE.parent, text=True
        ).strip()
        provenance = {"schemaRevision": revision, "schemas": {}}
        for path in sorted(source.glob("*.schema.json")):
            data = path.read_bytes()
            provenance["schemas"][path.name] = {
                "id": json.loads(data)["$id"],
                "digest": "sha256:" + hashlib.sha256(data).hexdigest(),
            }
    if not provenance["schemas"]:
        raise ValueError("empty schema inventory")
    actual = {p.name for p in source.glob("*.schema.json")}
    if actual != set(provenance["schemas"]):
        raise ValueError("schema source inventory mismatch")
    for name, expected in provenance["schemas"].items():
        data = (source / name).read_bytes()
        if "sha256:" + hashlib.sha256(data).hexdigest() != expected["digest"]:
            raise ValueError("schema source digest mismatch: " + name)
    return source, provenance


def copy_bundle(destination):
    source, provenance = bundle()
    destination.mkdir(parents=True, exist_ok=True)
    for path in destination.glob("*.schema.json"):
        path.unlink()  # Only this build's generated schema files.
    for name in provenance["schemas"]:
        shutil.copyfile(source / name, destination / name)
    (destination / "provenance.json").write_text(
        json.dumps(provenance, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


class BuildPython(build_py):
    def run(self):
        super().run()
        copy_bundle(Path(self.build_lib) / "agent_suite" / "_schemas")


class SourceDistribution(sdist):
    def make_release_tree(self, base_dir, files):
        super().make_release_tree(base_dir, files)
        copy_bundle(Path(base_dir) / "_schema_source")


setup(cmdclass={"build_py": BuildPython, "sdist": SourceDistribution})
