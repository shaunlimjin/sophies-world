import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import promote


def test_validate_promotion_approach_to_prod_raises(capsys):
    with pytest.raises(SystemExit):
        promote.validate_promotion("approach-b2-v2", "prod")
    captured = capsys.readouterr()
    assert "directly to prod" in captured.err


def test_validate_promotion_approach_to_staging_ok():
    promote.validate_promotion("approach-b2-v2", "staging")  # should not raise


def test_validate_promotion_staging_to_prod_ok():
    promote.validate_promotion("staging", "prod")  # should not raise


def test_get_source_dir_staging(tmp_path):
    result = promote.get_source_dir(tmp_path, "staging")
    assert result == tmp_path / "staging"


def test_get_source_dir_approach(tmp_path):
    result = promote.get_source_dir(tmp_path, "approach-b2-v2")
    assert result == tmp_path / "staging" / "approaches" / "approach-b2-v2"


def test_get_dest_dir_staging(tmp_path):
    result = promote.get_dest_dir(tmp_path, "staging")
    assert result == tmp_path / "staging"


def test_get_dest_dir_prod(tmp_path):
    result = promote.get_dest_dir(tmp_path, "prod")
    assert result == tmp_path


def test_compute_diff_detects_new_file(tmp_path):
    src = tmp_path / "staging" / "approaches" / "approach-b1"
    (src / "config").mkdir(parents=True)
    (src / "config" / "research.yaml").write_text("new: true")

    dest = tmp_path
    (dest / "config").mkdir(parents=True)

    changes = promote.compute_diff(src, dest)
    assert len(changes) == 1
    action, src_path, dest_path = changes[0]
    assert action == "add"
    assert dest_path == dest / "config" / "research.yaml"


def test_compute_diff_detects_modified_file(tmp_path):
    src = tmp_path / "staging" / "approaches" / "approach-b1"
    (src / "config").mkdir(parents=True)
    (src / "config" / "research.yaml").write_text("new: true")

    dest = tmp_path
    (dest / "config").mkdir(parents=True)
    (dest / "config" / "research.yaml").write_text("old: true")

    changes = promote.compute_diff(src, dest)
    assert len(changes) == 1
    assert changes[0][0] == "modify"


def test_compute_diff_no_changes_when_identical(tmp_path):
    src = tmp_path / "staging" / "approaches" / "approach-b1"
    (src / "config").mkdir(parents=True)
    (src / "config" / "research.yaml").write_text("same: true")

    dest = tmp_path
    (dest / "config").mkdir(parents=True)
    (dest / "config" / "research.yaml").write_text("same: true")

    changes = promote.compute_diff(src, dest)
    assert changes == []


def test_apply_promotion_copies_files(tmp_path):
    src_file = tmp_path / "src" / "config" / "research.yaml"
    src_file.parent.mkdir(parents=True)
    src_file.write_text("new: true")
    dest_file = tmp_path / "dest" / "config" / "research.yaml"

    promote.apply_promotion([("add", src_file, dest_file)])
    assert dest_file.exists()
    assert dest_file.read_text() == "new: true"
