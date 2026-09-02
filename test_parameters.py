import subprocess
import sys
import os
import shutil
import pytest

NODE_MODULES_PY = os.path.abspath(os.path.join(os.path.dirname(__file__), "node_modules.py"))

def test_cpio_without_legacy_container():
    """Verify that using --cpio without --legacy-container raises a command line validation error."""
    result = subprocess.run(
        [sys.executable, NODE_MODULES_PY, "--cpio", "test.obscpio"],
        capture_output=True,
        text=True
    )
    assert result.returncode != 0
    assert "--cpio can only be used when --legacy-container is enabled" in result.stderr

def test_legacy_container_and_cpio_accepted():
    """Verify that both --legacy-container and --cpio are accepted together (should not raise parser error)."""
    result = subprocess.run(
        [sys.executable, NODE_MODULES_PY, "--legacy-container", "--cpio", "test.obscpio", "--dry"],
        capture_output=True,
        text=True
    )
    assert "--cpio can only be used when --legacy-container is enabled" not in result.stderr

def test_node_dir_routing(tmp_path):
    """Verify that individual tarballs are routed into the specified node-dir when legacy-container is false."""
    parent_dir = tmp_path.parent
    lock_file = parent_dir / "package-lock.json"
    lock_file.write_text("""{
  "name": "simple-test",
  "version": "1.0.0",
  "lockfileVersion": 2,
  "requires": true,
  "dependencies": {
    "ms": {
      "version": "2.0.0",
      "resolved": "https://registry.npmjs.org/ms/-/ms-2.0.0.tgz",
      "integrity": "sha512-Tpp60P6IUJDTuOq/5Z8cdskzJujfwqfOTkrwIwj7IRISpnkJnT6SyJ4PCPnGMoFjC9ddhal5KVIYtAt97ix05A=="
    }
  }
}""")

    custom_node_dir = "custom_deps_folder"
    
    spec_file = parent_dir / "mock.spec"
    spec_file.write_text("# NODE_MODULES BEGIN\n# NODE_MODULES END\n")

    result = subprocess.run(
        [
            sys.executable,
            NODE_MODULES_PY,
            "-i", "package-lock.json",
            "--spec", "mock.spec",
            "--node-dir", custom_node_dir,
            "--outdir", str(tmp_path),
            "--download"
        ],
        capture_output=True,
        text=True,
        cwd=parent_dir
    )
    
    assert result.returncode == 0
    target_dir = tmp_path / custom_node_dir
    assert target_dir.is_dir()
    assert (target_dir / "ms-2.0.0.tgz").is_file()
