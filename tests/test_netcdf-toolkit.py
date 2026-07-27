#!/usr/bin/env python3
"""Tests for netcdf-toolkit CLI."""

import sys
import os
import json
import csv
import importlib.util
import unittest
from unittest.mock import patch, MagicMock

# Load the module
_script_path = os.path.join(os.path.dirname(__file__), "..", "scripts", "netcdf-toolkit.py")
_spec = importlib.util.spec_from_file_location("netcdf_toolkit", _script_path)
nct = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nct)


class TestParseBbox(unittest.TestCase):
    def test_valid_bbox(self):
        result = nct.parse_bbox("73,18,135,54")
        self.assertEqual(result, (73.0, 18.0, 135.0, 54.0))

    def test_invalid_format(self):
        self.assertIsNone(nct.parse_bbox("1,2,3"))
        self.assertIsNone(nct.parse_bbox("not,a,bbox,str"))

    def test_out_of_range(self):
        self.assertIsNone(nct.parse_bbox("73,18,135,100"))  # lat > 90
        self.assertIsNone(nct.parse_bbox("-200,18,135,54"))  # lon < -180

    def test_inverted(self):
        self.assertIsNone(nct.parse_bbox("135,18,73,54"))  # minlon > maxlon


class TestCmdInfo(unittest.TestCase):
    def test_file_not_found(self):
        args = nct.argparse.Namespace(input="/nonexistent/path.nc", json=False)
        rc = nct.cmd_info(args)
        self.assertEqual(rc, 1)


class TestCmdConvert(unittest.TestCase):
    def test_file_not_found(self):
        args = nct.argparse.Namespace(
            input="/nonexistent/path.nc", variable="temp",
            output="/tmp/out.tif", time_index=0,
        )
        rc = nct.cmd_convert(args)
        self.assertEqual(rc, 1)


class TestCmdExtract(unittest.TestCase):
    def test_file_not_found(self):
        args = nct.argparse.Namespace(
            input="/nonexistent/path.nc", variables="temp,pressure",
            output="/tmp/out.nc",
        )
        rc = nct.cmd_extract(args)
        self.assertEqual(rc, 1)


class TestCmdSubset(unittest.TestCase):
    def test_file_not_found(self):
        args = nct.argparse.Namespace(
            input="/nonexistent/path.nc", variable="temp",
            bbox="73,18,135,54", start=None, end=None,
            output="/tmp/out.tif", format="geotiff",
        )
        rc = nct.cmd_subset(args)
        self.assertEqual(rc, 1)

    def test_invalid_bbox(self):
        args = nct.argparse.Namespace(
            input="/nonexistent/path.nc", variable="temp",
            bbox="invalid", start=None, end=None,
            output="/tmp/out.tif", format="geotiff",
        )
        rc = nct.cmd_subset(args)
        self.assertEqual(rc, 1)


class TestFormatFlag(unittest.TestCase):
    """Tests for the --format flag on convert/subset/from-place subcommands."""

    def setUp(self):
        import tempfile
        self.tmpdir = tempfile.mkdtemp(prefix="netcdf_toolkit_test_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_fake_nc(self, name="fake.nc", with_latlon=True):
        """Create a minimal NetCDF file with one 2D variable."""
        import numpy as np
        try:
            from netCDF4 import Dataset
        except ImportError:
            import h5netcdf
            path = os.path.join(self.tmpdir, name)
            with h5netcdf.File(path, "w") as ds:
                ds.dimensions["lat"] = 4
                ds.dimensions["lon"] = 5
                if with_latlon:
                    v_lat = ds.create_variable("lat", ("lat",), dtype="f4")
                    v_lat[:] = [0.0, 1.0, 2.0, 3.0]
                    v_lon = ds.create_variable("lon", ("lon",), dtype="f4")
                    v_lon[:] = [10.0, 11.0, 12.0, 13.0, 14.0]
                v = ds.create_variable("temp", ("lat", "lon"), dtype="f4")
                v[:] = np.arange(20, dtype="f4").reshape(4, 5)
            return path
        path = os.path.join(self.tmpdir, name)
        ds = Dataset(path, "w", format="NETCDF4_CLASSIC")
        ds.createDimension("lat", 4)
        ds.createDimension("lon", 5)
        if with_latlon:
            lat = ds.createVariable("lat", "f4", ("lat",))
            lon = ds.createVariable("lon", "f4", ("lon",))
            lat[:] = [0.0, 1.0, 2.0, 3.0]
            lon[:] = [10.0, 11.0, 12.0, 13.0, 14.0]
        v = ds.createVariable("temp", "f4", ("lat", "lon"))
        v[:] = np.arange(20, dtype="f4").reshape(4, 5)
        ds.close()
        return path

    def test_convert_help_lists_format(self):
        """The --format choice should be visible in --help output."""
        import subprocess
        out = subprocess.run(
            [sys.executable,
             os.path.join(os.path.dirname(__file__), "..", "scripts", "netcdf-toolkit.py"),
             "convert", "--help"],
            capture_output=True, text=True, timeout=10,
        )
        text = out.stdout + out.stderr
        self.assertIn("--format", text)
        self.assertIn("geojson", text)
        self.assertIn("csv", text)

    def test_subset_help_lists_format(self):
        import subprocess
        out = subprocess.run(
            [sys.executable,
             os.path.join(os.path.dirname(__file__), "..", "scripts", "netcdf-toolkit.py"),
             "subset", "--help"],
            capture_output=True, text=True, timeout=10,
        )
        text = out.stdout + out.stderr
        self.assertIn("--format", text)
        self.assertIn("geojson", text)
        self.assertIn("csv", text)

    def test_from_place_help_lists_format(self):
        import subprocess
        out = subprocess.run(
            [sys.executable,
             os.path.join(os.path.dirname(__file__), "..", "scripts", "netcdf-toolkit.py"),
             "from-place", "--help"],
            capture_output=True, text=True, timeout=10,
        )
        text = out.stdout + out.stderr
        self.assertIn("--format", text)

    def test_convert_geojson(self):
        """--format geojson on convert should write a .geojson next to --output."""
        path = self._make_fake_nc()
        out_path = os.path.join(self.tmpdir, "out.tif")
        args = nct.argparse.Namespace(
            input=path, variable="temp", output=out_path,
            time_index=0, format="geojson",
        )
        rc = nct.cmd_convert(args)
        self.assertEqual(rc, 0)
        gj_path = os.path.join(self.tmpdir, "out.geojson")
        self.assertTrue(os.path.exists(gj_path), f"missing {gj_path}")
        with open(gj_path, encoding="utf-8") as f:
            fc = json.load(f)
        self.assertEqual(fc["type"], "FeatureCollection")
        self.assertEqual(len(fc["features"]), 1)
        feat = fc["features"][0]
        self.assertEqual(feat["geometry"]["type"], "Polygon")
        self.assertEqual(feat["properties"]["variable"], "temp")
        self.assertIn("min", feat["properties"])
        self.assertIn("max", feat["properties"])
        self.assertIn("mean", feat["properties"])
        # No GeoTIFF should be written for geojson
        self.assertFalse(os.path.exists(out_path))

    def test_convert_csv(self):
        """--format csv on convert should write a .csv with stats."""
        path = self._make_fake_nc()
        out_path = os.path.join(self.tmpdir, "out.tif")
        args = nct.argparse.Namespace(
            input=path, variable="temp", output=out_path,
            time_index=0, format="csv",
        )
        rc = nct.cmd_convert(args)
        self.assertEqual(rc, 0)
        csv_path = os.path.join(self.tmpdir, "out.csv")
        self.assertTrue(os.path.exists(csv_path))
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
        self.assertEqual(rows[0][0], "variable")
        self.assertEqual(rows[1][0], "temp")
        self.assertEqual(rows[1][5], "5")  # width
        self.assertEqual(rows[1][6], "4")  # height
        self.assertFalse(os.path.exists(out_path))

    def test_convert_default_is_geotiff(self):
        """No --format → existing GeoTIFF behavior is preserved."""
        path = self._make_fake_nc()
        out_path = os.path.join(self.tmpdir, "out.tif")
        args = nct.argparse.Namespace(
            input=path, variable="temp", output=out_path,
            time_index=0, format="geotiff",
        )
        rc = nct.cmd_convert(args)
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(out_path))
        self.assertFalse(os.path.exists(os.path.join(self.tmpdir, "out.geojson")))
        self.assertFalse(os.path.exists(os.path.join(self.tmpdir, "out.csv")))

    def test_subset_geojson(self):
        path = self._make_fake_nc()
        out_path = os.path.join(self.tmpdir, "subset.tif")
        args = nct.argparse.Namespace(
            input=path, variable="temp", bbox="11,1,13,2",
            start=None, end=None, output=out_path, format="geojson",
        )
        rc = nct.cmd_subset(args)
        self.assertEqual(rc, 0)
        gj_path = os.path.join(self.tmpdir, "subset.geojson")
        self.assertTrue(os.path.exists(gj_path))
        with open(gj_path, encoding="utf-8") as f:
            fc = json.load(f)
        self.assertEqual(fc["features"][0]["properties"]["variable"], "temp")
        # Subset should have requested_bbox in properties
        self.assertIn("requested_bbox", fc["features"][0]["properties"])


class TestWriteAltFormatHelpers(unittest.TestCase):
    """Direct unit tests for write_alt_format / _compute_stats."""

    def setUp(self):
        import tempfile
        self.tmpdir = tempfile.mkdtemp(prefix="netcdf_altfmt_")
        import numpy as np
        self.arr = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], dtype="f4")
        self.bounds = (10.0, 20.0, 13.0, 22.0)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_geojson_write(self):
        out = os.path.join(self.tmpdir, "x.tif")
        nct.write_alt_format("geojson", out, self.arr, self.bounds,
                             variable="temp", extra={"k": 1})
        gj = out[:-4] + ".geojson"
        self.assertTrue(os.path.exists(gj))
        with open(gj, encoding="utf-8") as f:
            d = json.load(f)
        self.assertEqual(d["type"], "FeatureCollection")
        self.assertEqual(d["features"][0]["properties"]["variable"], "temp")
        self.assertEqual(d["features"][0]["properties"]["k"], 1)
        self.assertEqual(d["features"][0]["properties"]["min"], 1.0)
        self.assertEqual(d["features"][0]["properties"]["max"], 6.0)

    def test_csv_write(self):
        out = os.path.join(self.tmpdir, "x.tif")
        nct.write_alt_format("csv", out, self.arr, self.bounds, variable="temp")
        c = out[:-4] + ".csv"
        self.assertTrue(os.path.exists(c))
        with open(c, encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        self.assertEqual(rows[0][0], "variable")
        self.assertEqual(rows[1][0], "temp")
        self.assertEqual(rows[1][1], "10.0")  # min_lon

    def test_geojson_with_explicit_geojson_ext_kept(self):
        out = os.path.join(self.tmpdir, "x.geojson")
        nct.write_alt_format("geojson", out, self.arr, self.bounds, variable="temp")
        self.assertTrue(os.path.exists(out))

    def test_compute_stats_basic(self):
        stats = nct._compute_stats(self.arr)
        self.assertEqual(stats["count"], 6)
        self.assertEqual(stats["min"], 1.0)
        self.assertEqual(stats["max"], 6.0)
        self.assertAlmostEqual(stats["mean"], 3.5, places=4)


if __name__ == "__main__":
    unittest.main()
