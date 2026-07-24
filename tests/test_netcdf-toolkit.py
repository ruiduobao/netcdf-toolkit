#!/usr/bin/env python3
"""Tests for netcdf-toolkit CLI."""

import sys
import os
import json
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
            output="/tmp/out.tif",
        )
        rc = nct.cmd_subset(args)
        self.assertEqual(rc, 1)

    def test_invalid_bbox(self):
        args = nct.argparse.Namespace(
            input="/nonexistent/path.nc", variable="temp",
            bbox="invalid", start=None, end=None,
            output="/tmp/out.tif",
        )
        rc = nct.cmd_subset(args)
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
