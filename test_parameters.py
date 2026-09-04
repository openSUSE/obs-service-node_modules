import subprocess
import sys
import os
import shutil
import pytest

NODE_MODULES_PY = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "node_modules.py")
)


def test_cpio_without_legacy_container():
    """Verify that using --cpio without --legacy-container raises a command line validation error."""
    result = subprocess.run(
        [sys.executable, NODE_MODULES_PY, "--cpio", "test.obscpio"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "--cpio is not recommended for Git Workflow projects" in result.stderr


def test_legacy_container_and_cpio_accepted():
    """Verify that both --legacy-container and --cpio are accepted together (should not raise parser error)."""
    result = subprocess.run(
        [
            sys.executable,
            NODE_MODULES_PY,
            "--legacy-container",
            "--cpio",
            "test.obscpio",
            "--dry",
        ],
        capture_output=True,
        text=True,
    )
    assert (
        "--cpio can only be used when --legacy-container is enabled"
        not in result.stderr
    )


def test_legacy_container_parameter_values():
    """Verify that --legacy-container accepts truthy, falsy, and empty string values correctly."""
    # 1. Test truthy value '1'
    result = subprocess.run(
        [
            sys.executable,
            NODE_MODULES_PY,
            "--legacy-container", "1",
            "--cpio", "test.obscpio",
            "--dry",
        ],
        capture_output=True,
        text=True,
    )
    assert "--cpio is not recommended" not in result.stderr

    # 2. Test empty string '' (which is passed by OBS for valueless parameter elements)
    result = subprocess.run(
        [
            sys.executable,
            NODE_MODULES_PY,
            "--legacy-container", "",
            "--cpio", "test.obscpio",
            "--dry",
        ],
        capture_output=True,
        text=True,
    )
    assert "--cpio is not recommended" not in result.stderr

    # 3. Test falsy value '0'
    result = subprocess.run(
        [
            sys.executable,
            NODE_MODULES_PY,
            "--legacy-container", "0",
            "--cpio", "test.obscpio",
            "--dry",
        ],
        capture_output=True,
        text=True,
    )
    assert "--cpio is not recommended" in result.stderr

    # 4. Test falsy value 'disable'
    result = subprocess.run(
        [
            sys.executable,
            NODE_MODULES_PY,
            "--legacy-container", "disable",
            "--cpio", "test.obscpio",
            "--dry",
        ],
        capture_output=True,
        text=True,
    )
    assert "--cpio is not recommended" in result.stderr

    # 5. Test invalid value 'invalid_val'
    result = subprocess.run(
        [
            sys.executable,
            NODE_MODULES_PY,
            "--legacy-container", "invalid_val",
            "--cpio", "test.obscpio",
            "--dry",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Boolean value expected, got invalid_val" in result.stderr


def test_output_file_gated_by_legacy_container(tmp_path):
    """Verify that the --output file (e.g. node_modules.spec.inc) is only generated when --legacy-container is enabled."""
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

    spec_file = parent_dir / "mock.spec"
    spec_file.write_text("# NODE_MODULES BEGIN\n# NODE_MODULES END\n")

    output_inc_file = tmp_path / "node_modules.spec.inc"

    # 1. Run WITHOUT --legacy-container but with --output
    # Note: --output should NOT be written
    result = subprocess.run(
        [
            sys.executable,
            NODE_MODULES_PY,
            "-i",
            "package-lock.json",
            "--spec",
            "mock.spec",
            "--output",
            "node_modules.spec.inc",
            "--node-dir",
            "node_modules",
            "--outdir",
            str(tmp_path),
            "--download",
        ],
        capture_output=True,
        text=True,
        cwd=parent_dir,
    )
    assert result.returncode == 0
    assert not output_inc_file.exists()

    # 2. Run WITH --legacy-container and --output
    # Note: --output should be written
    result = subprocess.run(
        [
            sys.executable,
            NODE_MODULES_PY,
            "-i",
            "package-lock.json",
            "--spec",
            "mock.spec",
            "--output",
            "node_modules.spec.inc",
            "--legacy-container",
            "--outdir",
            str(tmp_path),
            "--download",
        ],
        capture_output=True,
        text=True,
        cwd=parent_dir,
    )
    assert result.returncode == 0
    assert output_inc_file.is_file()


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
            "-i",
            "package-lock.json",
            "--spec",
            "mock.spec",
            "--node-dir",
            custom_node_dir,
            "--outdir",
            str(tmp_path),
            "--download",
        ],
        capture_output=True,
        text=True,
        cwd=parent_dir,
    )

    assert result.returncode == 0
    target_dir = tmp_path / custom_node_dir
    assert target_dir.is_dir()
    assert (target_dir / "ms-2.0.0.tgz").is_file()


def test_unneeded_files_cleanup(tmp_path):
    """Verify that unneeded files are removed from the node-dir when --cpio is not used."""
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

    custom_node_dir = "node_modules"
    spec_file = parent_dir / "mock.spec"
    spec_file.write_text("# NODE_MODULES BEGIN\n# NODE_MODULES END\n")

    # 1. Run first download
    result = subprocess.run(
        [
            sys.executable,
            NODE_MODULES_PY,
            "-i",
            "package-lock.json",
            "--spec",
            "mock.spec",
            "--node-dir",
            custom_node_dir,
            "--outdir",
            str(tmp_path),
            "--download",
        ],
        capture_output=True,
        text=True,
        cwd=parent_dir,
    )
    assert result.returncode == 0
    target_dir = tmp_path / custom_node_dir
    assert target_dir.is_dir()
    needed_file = target_dir / "ms-2.0.0.tgz"
    assert needed_file.is_file()

    # 2. Add an unneeded file
    unneeded_file = target_dir / "obsolete-file.tgz"
    unneeded_file.write_text("dummy content")
    assert unneeded_file.is_file()

    # 3. Run again and assert cleanup
    result = subprocess.run(
        [
            sys.executable,
            NODE_MODULES_PY,
            "-i",
            "package-lock.json",
            "--spec",
            "mock.spec",
            "--node-dir",
            custom_node_dir,
            "--outdir",
            str(tmp_path),
            "--download",
        ],
        capture_output=True,
        text=True,
        cwd=parent_dir,
    )
    assert result.returncode == 0
    assert needed_file.is_file()
    assert not unneeded_file.exists()


def test_unneeded_files_cleanup_safety_guard(tmp_path):
    """Verify that unneeded files are NOT removed if the download directory is the current directory (safety guard)."""
    lock_file = tmp_path / "package-lock.json"
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

    spec_file = tmp_path / "mock.spec"
    spec_file.write_text("# NODE_MODULES BEGIN\n# NODE_MODULES END\n")

    # Run inside tmp_path, without --outdir and with --legacy-container (so target_dir defaults to current working directory, i.e., tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            NODE_MODULES_PY,
            "-i",
            "package-lock.json",
            "--spec",
            "mock.spec",
            "--legacy-container",
            "--download",
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert result.returncode == 0
    needed_file = tmp_path / "ms-2.0.0.tgz"
    assert needed_file.is_file()

    # Place an unneeded file in the same directory (tmp_path)
    unneeded_file = tmp_path / "obsolete-file.tgz"
    unneeded_file.write_text("dummy content")
    assert unneeded_file.is_file()

    # Run again, verify safety guard keeps unneeded_file intact
    result = subprocess.run(
        [
            sys.executable,
            NODE_MODULES_PY,
            "-i",
            "package-lock.json",
            "--spec",
            "mock.spec",
            "--legacy-container",
            "--download",
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert result.returncode == 0
    assert needed_file.is_file()
    assert unneeded_file.is_file()  # Safety guard kept it!


def test_osc_directory_rename_consecutive_runs(tmp_path):
    """Simulate osc's consecutive runs where a temp dir's node_modules is moved/renamed to the package dir."""
    package_dir = tmp_path / "package"
    package_dir.mkdir()

    lock_file = package_dir / "package-lock.json"
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

    spec_file = package_dir / "mock.spec"
    spec_file.write_text("# NODE_MODULES BEGIN\n# NODE_MODULES END\n")

    # RUN 1:
    temp_dir_1 = package_dir / "temp_dir_1"
    temp_dir_1.mkdir()

    result = subprocess.run(
        [
            sys.executable,
            NODE_MODULES_PY,
            "-i",
            "package-lock.json",
            "--spec",
            "mock.spec",
            "--node-dir",
            "node_modules",
            "--outdir",
            str(temp_dir_1),
            "--download",
        ],
        capture_output=True,
        text=True,
        cwd=package_dir,
    )
    assert result.returncode == 0

    # Simulate osc moving temp_dir_1/node_modules to package_dir/node_modules
    os.rename(temp_dir_1 / "node_modules", package_dir / "node_modules")
    assert (package_dir / "node_modules" / "ms-2.0.0.tgz").is_file()

    # RUN 2:
    temp_dir_2 = package_dir / "temp_dir_2"
    temp_dir_2.mkdir()

    result = subprocess.run(
        [
            sys.executable,
            NODE_MODULES_PY,
            "-i",
            "package-lock.json",
            "--spec",
            "mock.spec",
            "--node-dir",
            "node_modules",
            "--outdir",
            str(temp_dir_2),
            "--download",
        ],
        capture_output=True,
        text=True,
        cwd=package_dir,
    )
    assert result.returncode == 0

    # Simulate osc moving temp_dir_2/node_modules to package_dir/node_modules
    # On unpatched code, this will raise OSError because package_dir/node_modules exists and is not empty.
    os.rename(temp_dir_2 / "node_modules", package_dir / "node_modules")
    assert (package_dir / "node_modules" / "ms-2.0.0.tgz").is_file()


def test_existing_file_checksum_verification(tmp_path):
    """Verify that an existing file with a mismatched checksum is re-downloaded."""
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

    custom_node_dir = "node_modules"
    spec_file = parent_dir / "mock.spec"
    spec_file.write_text("# NODE_MODULES BEGIN\n# NODE_MODULES END\n")

    # 1. First run: download the file
    result = subprocess.run(
        [
            sys.executable,
            NODE_MODULES_PY,
            "-i",
            "package-lock.json",
            "--spec",
            "mock.spec",
            "--node-dir",
            custom_node_dir,
            "--outdir",
            str(tmp_path),
            "--download",
        ],
        capture_output=True,
        text=True,
        cwd=parent_dir,
    )
    assert result.returncode == 0
    target_file = tmp_path / custom_node_dir / "ms-2.0.0.tgz"
    assert target_file.is_file()
    original_size = target_file.stat().st_size

    # 2. Corrupt the file
    target_file.write_text("corrupted content")
    assert target_file.stat().st_size != original_size

    # 3. Second run: should notice the mismatch and re-download
    result = subprocess.run(
        [
            sys.executable,
            NODE_MODULES_PY,
            "-i",
            "package-lock.json",
            "--spec",
            "mock.spec",
            "--node-dir",
            custom_node_dir,
            "--outdir",
            str(tmp_path),
            "--download",
            "--verbose",
        ],
        capture_output=True,
        text=True,
        cwd=parent_dir,
    )
    assert result.returncode == 0
    assert target_file.stat().st_size == original_size
    assert "checksum failure for existing ms-2.0.0.tgz, re-downloading" in result.stderr


def test_obscpio_checksum_verification(tmp_path):
    """Verify that a corrupted file inside a .obscpio legacy container is detected and re-downloaded."""
    import sys

    lock_file = tmp_path / "package-lock.json"
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

    spec_file = tmp_path / "mock.spec"
    spec_file.write_text("# NODE_MODULES BEGIN\n# NODE_MODULES END\n")

    # Write a corrupt node_modules.obscpio using CpioWriter imported from node_modules.py
    sys.path.insert(0, os.path.dirname(NODE_MODULES_PY))
    from node_modules import CpioWriter, CpioReader

    cpio_path = tmp_path / "node_modules.obscpio"
    with CpioWriter(str(cpio_path)) as c:
        c.add("ms-2.0.0.tgz", b"corrupted cpio content")

    # Run the service with legacy-container and cpio options
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    result = subprocess.run(
        [
            sys.executable,
            NODE_MODULES_PY,
            "-i",
            "package-lock.json",
            "--spec",
            "mock.spec",
            "--legacy-container",
            "--cpio",
            "node_modules.obscpio",
            "--outdir",
            str(out_dir),
            "--download",
            "--verbose",
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )

    assert result.returncode == 0
    assert "checksum failure for existing ms-2.0.0.tgz, re-downloading" in result.stderr

    # Verify that the final cpio file exists in out_dir and contains the correctly downloaded file (not corrupted)
    final_cpio = out_dir / "node_modules.obscpio"
    assert final_cpio.is_file()

    # Extract final cpio and check file contents size (it should be original correct size, not corrupted size)
    ext_dir = tmp_path / "extracted"
    ext_dir.mkdir()
    CpioReader(str(final_cpio)).extract(str(ext_dir))

    extracted_file = ext_dir / "ms-2.0.0.tgz"
    assert extracted_file.is_file()
    assert extracted_file.stat().st_size > 2000  # ms-2.0.0.tgz size is ~2.3kb


def test_include_file_sources_with_and_without_legacy_container(tmp_path):
    """Verify that the include file (or spec file) correctly takes care of the subfolder when not using obscpio."""
    parent_dir = tmp_path / "parent"
    parent_dir.mkdir()
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

    # Case 1: Without legacy container (i.e. not using obscpio, git workflow)
    # The Source URL must prepend the node-dir subfolder
    out_dir_git = tmp_path / "out_git"
    out_dir_git.mkdir()
    spec_file_git = parent_dir / "mock_git.spec"
    spec_file_git.write_text("# NODE_MODULES BEGIN\n# NODE_MODULES END\n")

    result_git = subprocess.run(
        [
            sys.executable,
            NODE_MODULES_PY,
            "-i",
            "package-lock.json",
            "--spec",
            "mock_git.spec",
            "--node-dir",
            "my_custom_dir",
            "--outdir",
            str(out_dir_git),
        ],
        capture_output=True,
        text=True,
        cwd=parent_dir,
    )
    assert result_git.returncode == 0
    # Since legacy-container is disabled, mock_git.spec is NOT processed or written to outdir
    assert not (out_dir_git / "mock_git.spec").exists()

    # Case 2: With legacy container (i.e. using obscpio)
    # The Source URL must NOT prepend the node-dir subfolder
    out_dir_legacy = tmp_path / "out_legacy"
    out_dir_legacy.mkdir()
    spec_file_legacy = parent_dir / "mock_legacy.spec"
    spec_file_legacy.write_text("# NODE_MODULES BEGIN\n# NODE_MODULES END\n")

    result_legacy = subprocess.run(
        [
            sys.executable,
            NODE_MODULES_PY,
            "-i",
            "package-lock.json",
            "--spec",
            "mock_legacy.spec",
            "--legacy-container",
            "--cpio",
            "node_modules.obscpio",
            "--node-dir",
            "my_custom_dir",
            "--outdir",
            str(out_dir_legacy),
        ],
        capture_output=True,
        text=True,
        cwd=parent_dir,
    )
    assert result_legacy.returncode == 0
    spec_content_legacy = (out_dir_legacy / "mock_legacy.spec").read_text()
    assert "https://registry.npmjs.org/ms/-/ms-2.0.0.tgz#/ms-2.0.0.tgz" in spec_content_legacy
