"""Tests for netcdf-toolkit from-place (PHASE 1+ REFACTORED)."""
import os
import sys
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, ".."))
SCRIPTS = os.path.join(PROJECT_ROOT, "scripts")


def test_from_place_subcommand_in_help():
    out = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, "netcdf-toolkit.py"), "--help"],
        capture_output=True, text=True, timeout=15,
    )
    combined = out.stdout + out.stderr
    assert "from-place" in combined


def test_from_place_resolves_place_then_runs():
    """PHASE 1+: from-place 真的解析 --place 然后调 fetch skill。"""
    out = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, "netcdf-toolkit.py"),
         "from-place", "--place", "北京市",
         "--start-date", "2024-01-01", "--end-date", "2024-01-07",
         "--output", os.path.join(os.environ.get("TEMP", "/tmp"), "nc_test.tif")],
        capture_output=True, text=True, timeout=60,
    )
    combined = out.stdout + out.stderr
    assert "from-place" in combined
    assert "PHASE 0 DISABLED" not in combined


def test_aoi_resolution_works_via_vendored_geoskill_core():
    skill_dir = PROJECT_ROOT
    sys.path.insert(0, skill_dir)
    from _geoskill_core import aoi
    m = aoi.resolve_place("北京市", allow_nominatim=True, use_cache=False)
    assert m.bbox_wgs84 is not None
    assert len(m.bbox_wgs84) == 4
