import hashlib
import json
import os
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import pytest


ROOT = Path(__file__).parents[3]
SEED = ROOT / "process/bench/cases/J03-document-flow/seed"
LOCK = ROOT / "process/bench/cases/J03-document-flow/dependencies.lock.json"
NS = {"m": "http://maven.apache.org/POM/4.0.0"}
MODULES = ("shared-contracts", "document-service", "workflow-service", "audit-service")


class InventoryError(ValueError):
    pass


def _load_lock(path=LOCK):
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_cache(lock, repository):
    for artifact in lock["artifacts"]:
        path = repository.joinpath(*artifact["path"].split("/"))
        if not path.is_file():
            raise InventoryError(f"missing cached artifact: {artifact['path']}")
        data = path.read_bytes()
        if len(data) != artifact["byte_length"] or hashlib.sha256(data).hexdigest() != artifact["sha256"]:
            raise InventoryError(f"modified cached artifact: {artifact['path']}")


def test_reactor_and_modules_are_exactly_pinned():
    tree = ET.parse(SEED / "pom.xml")
    root = tree.getroot()
    assert root.findtext("m:modelVersion", namespaces=NS) == "4.0.0"
    assert root.findtext("m:packaging", namespaces=NS) == "pom"
    assert [node.text for node in root.findall("m:modules/m:module", NS)] == list(MODULES)
    properties = {node.tag.rsplit("}", 1)[-1]: node.text for node in root.find("m:properties", NS)}
    assert properties["java.version"] == "21"
    assert properties["maven.compiler.release"] == "21"
    assert properties["spring-boot.version"] == "3.5.11"
    assert properties["maven-enforcer-plugin.version"]
    assert properties["maven-compiler-plugin.version"]
    assert properties["maven-surefire-plugin.version"]
    assert properties["maven-failsafe-plugin.version"]
    for module in MODULES:
        child = ET.parse(SEED / module / "pom.xml").getroot()
        assert child.findtext("m:parent/m:relativePath", namespaces=NS) == "../pom.xml"
        assert child.findtext("m:artifactId", namespaces=NS) == module


def test_java_21_and_maven_are_enforced_before_build():
    root = ET.parse(SEED / "pom.xml").getroot()
    plugins = {
        node.findtext("m:artifactId", namespaces=NS): node
        for node in root.findall("m:build/m:pluginManagement/m:plugins/m:plugin", NS)
    }
    enforcer = plugins["maven-enforcer-plugin"]
    xml = ET.tostring(enforcer, encoding="unicode")
    assert "requireJavaVersion" in xml and "[21,22)" in xml
    assert "requireMavenVersion" in xml and "[3.9.12,3.9.13)" in xml
    assert "requirePluginVersions" in xml


def test_dependency_lock_is_closed_sorted_and_portable():
    lock = _load_lock()
    assert lock["schema_version"] == 1
    assert lock["java_major"] == 21
    assert lock["maven_version"] == "3.9.12"
    assert lock["source_repository"] == "https://repo.maven.apache.org/maven2"
    artifacts = lock["artifacts"]
    paths = [item["path"] for item in artifacts]
    assert paths == sorted(paths) and len(paths) == len(set(paths))
    assert artifacts and any(path.endswith(".jar") for path in paths) and any(path.endswith(".pom") for path in paths)
    for artifact in artifacts:
        assert not Path(artifact["path"]).is_absolute()
        assert "\\" not in artifact["path"] and ".." not in artifact["path"].split("/")
        assert re.fullmatch(r"[0-9a-f]{64}", artifact["sha256"])
        assert artifact["byte_length"] > 0


def test_missing_or_modified_cache_artifact_fails_closed(tmp_path):
    artifact = {"path": "g/a/1/a-1.jar", "sha256": hashlib.sha256(b"good").hexdigest(), "byte_length": 4}
    lock = {"artifacts": [artifact]}
    with pytest.raises(InventoryError, match="missing cached artifact"):
        _verify_cache(lock, tmp_path)
    path = tmp_path / "g/a/1/a-1.jar"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"evil")
    with pytest.raises(InventoryError, match="modified cached artifact"):
        _verify_cache(lock, tmp_path)


def test_provisioned_cache_matches_every_recorded_hash_when_selected():
    repository = os.environ.get("J03_MAVEN_REPOSITORY")
    if repository is None:
        # Portable source check; the card's recorded Green command supplies the
        # external sealed-cache path and exercises every byte hash.
        assert _load_lock()["artifacts"]
        return
    _verify_cache(_load_lock(), Path(repository))
