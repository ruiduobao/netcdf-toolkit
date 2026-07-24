#!/usr/bin/env python3
"""
NetCDF Toolkit CLI — Convert, extract, subset, and inspect NetCDF/HDF files.

Privacy Notice:
    ALL processing is local. No data is uploaded or transmitted anywhere.
    This tool only reads from and writes to your local filesystem.

Data Source:
    Local NetCDF/HDF files (no download required).

License: MIT-0
Author: ruiduobao
Version: 0.1.0
"""

import argparse
import json
import sys
import os
from typing import List, Dict, Any, Optional, Tuple

try:
    import numpy as np
except ImportError:
    print("ERROR: 'numpy' is required. Install with: pip install numpy")
    sys.exit(1)

try:
    from netCDF4 import Dataset
except ImportError:
    try:
        import h5netcdf
        Dataset = h5netcdf.File
    except ImportError:
        print("ERROR: 'netCDF4' or 'h5netcdf' is required.")
        print("Install with: pip install netCDF4 rasterio numpy")
        sys.exit(1)

try:
    import rasterio
    from rasterio.transform import from_bounds
except ImportError:
    rasterio = None  # type: ignore


def check_rasterio():
    """Check if rasterio is available."""
    if rasterio is None:
        print("ERROR: 'rasterio' is required for GeoTIFF output.")
        print("Install with: pip install rasterio")
        sys.exit(1)


def parse_bbox(bbox_str: str) -> Optional[Tuple[float, float, float, float]]:
    """Parse bbox string 'minlon,minlat,maxlon,maxlat' into tuple."""
    try:
        parts = [float(x.strip()) for x in bbox_str.split(",")]
        if len(parts) != 4:
            return None
        minlon, minlat, maxlon, maxlat = parts
        if not (-180 <= minlon <= 180 and -180 <= maxlon <= 180):
            return None
        if not (-90 <= minlat <= 90 and -90 <= maxlat <= 90):
            return None
        if minlon >= maxlon or minlat >= maxlat:
            return None
        return (minlon, minlat, maxlon, maxlat)
    except (ValueError, AttributeError):
        return None


def cmd_info(args: argparse.Namespace) -> int:
    """Handle the 'info' subcommand."""
    input_path = args.input
    if not os.path.isfile(input_path):
        print(f"ERROR: File '{input_path}' not found.", file=sys.stderr)
        return 1

    try:
        with Dataset(input_path, "r") as ds:
            info = {
                "file": input_path,
                "dimensions": {name: len(dim) for name, dim in ds.dimensions.items()},
                "variables": {},
                "global_attributes": {attr: str(getattr(ds, attr)) for attr in ds.ncattrs()},
            }
            for name, var in ds.variables.items():
                var_info = {
                    "shape": list(var.shape),
                    "dtype": str(var.dtype),
                    "dimensions": list(var.dimensions),
                }
                # Add variable attributes
                for attr in var.ncattrs():
                    val = getattr(var, attr)
                    try:
                        var_info[attr] = val.item() if hasattr(val, "item") else str(val)
                    except Exception:
                        var_info[attr] = str(val)
                info["variables"][name] = var_info
    except Exception as e:
        print(f"ERROR: Failed to read file: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(info, indent=2, ensure_ascii=False))
    else:
        print(f"File: {info['file']}")
        print(f"\nDimensions:")
        for name, size in info["dimensions"].items():
            print(f"  {name}: {size}")
        print(f"\nVariables ({len(info['variables'])}):")
        for name, vi in info["variables"].items():
            print(f"  {name}: shape={vi['shape']}, dtype={vi['dtype']}, dims={vi['dimensions']}")
            for k, v in vi.items():
                if k not in ("shape", "dtype", "dimensions"):
                    print(f"    {k}: {v}")
        if info["global_attributes"]:
            print(f"\nGlobal Attributes:")
            for k, v in info["global_attributes"].items():
                print(f"  {k}: {v}")
    return 0


def cmd_convert(args: argparse.Namespace) -> int:
    """Handle the 'convert' subcommand."""
    check_rasterio()
    input_path = args.input
    variable = args.variable
    output_path = args.output
    time_index = args.time_index

    if not os.path.isfile(input_path):
        print(f"ERROR: File '{input_path}' not found.", file=sys.stderr)
        return 1

    try:
        with Dataset(input_path, "r") as ds:
            if variable not in ds.variables:
                available = list(ds.variables.keys())
                print(f"ERROR: Variable '{variable}' not found. Available: {available}", file=sys.stderr)
                return 1

            var = ds.variables[variable]
            data = var[:]

            # Handle time dimension
            if data.ndim >= 3 and time_index >= data.shape[0]:
                print(f"ERROR: time_index {time_index} out of range (max {data.shape[0] - 1}).", file=sys.stderr)
                return 1

            if data.ndim >= 3:
                data = data[time_index] if time_index < data.shape[0] else data[0]

            # Ensure 2D
            if data.ndim > 2:
                data = data[0]
            if data.ndim < 2:
                print(f"ERROR: Variable has {data.ndim} dimensions. Need at least 2D.", file=sys.stderr)
                return 1

            # Get coordinates
            lats = None
            lons = None
            for coord_name in ["lat", "latitude", "y", "Latitude", "Lat"]:
                if coord_name in ds.variables:
                    lats = ds.variables[coord_name][:]
                    break
            for coord_name in ["lon", "longitude", "x", "Longitude", "Lon"]:
                if coord_name in ds.variables:
                    lons = ds.variables[coord_name][:]
                    break

            if lats is not None and lons is not None:
                if lats.ndim == 1 and lons.ndim == 1:
                    minlon, maxlon = float(lons.min()), float(lons.max())
                    minlat, maxlat = float(lats.min()), float(lats.max())
                    transform = from_bounds(minlon, minlat, maxlon, maxlat, data.shape[1], data.shape[0])
                elif lats.ndim == 2 and lons.ndim == 2:
                    minlon, maxlon = float(lons.min()), float(lons.max())
                    minlat, maxlat = float(lats.min()), float(lats.max())
                    transform = from_bounds(minlon, minlat, maxlon, maxlat, data.shape[1], data.shape[0])
                else:
                    transform = rasterio.transform.from_origin(0, 0, 1, 1)
            else:
                transform = rasterio.transform.from_origin(0, 0, 1, 1)

            # Write GeoTIFF
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            with rasterio.open(
                output_path,
                "w",
                driver="GTiff",
                height=data.shape[0],
                width=data.shape[1],
                count=1,
                dtype=data.dtype,
                crs="EPSG:4326",
                transform=transform,
            ) as dst:
                dst.write(data, 1)

            print(f"Wrote {output_path} ({data.shape[1]}x{data.shape[0]})")
            return 0

    except Exception as e:
        print(f"ERROR: Conversion failed: {e}", file=sys.stderr)
        return 1


def cmd_extract(args: argparse.Namespace) -> int:
    """Handle the 'extract' subcommand."""
    input_path = args.input
    variables = [v.strip() for v in args.variables.split(",")]
    output_path = args.output

    if not os.path.isfile(input_path):
        print(f"ERROR: File '{input_path}' not found.", file=sys.stderr)
        return 1

    try:
        with Dataset(input_path, "r") as src:
            # Validate variables
            for v in variables:
                if v not in src.variables:
                    print(f"ERROR: Variable '{v}' not found. Available: {list(src.variables.keys())}", file=sys.stderr)
                    return 1

            # Create output file
            with Dataset(output_path, "w") as dst:
                # Copy dimensions
                for name, dim in src.dimensions.items():
                    dst.createDimension(name, len(dim) if not dim.isunlimited() else None)

                # Copy selected variables
                for name in variables:
                    var = src.variables[name]
                    new_var = dst.createVariable(name, var.dtype, var.dimensions)
                    new_var[:] = var[:]
                    for attr in var.ncattrs():
                        setattr(new_var, attr, getattr(var, attr))

                # Copy global attributes
                for attr in src.ncattrs():
                    setattr(dst, attr, getattr(src, attr))

        print(f"Extracted {len(variables)} variable(s) to {output_path}")
        return 0

    except Exception as e:
        print(f"ERROR: Extraction failed: {e}", file=sys.stderr)
        return 1


def cmd_subset(args: argparse.Namespace) -> int:
    """Handle the 'subset' subcommand."""
    check_rasterio()
    input_path = args.input
    variable = args.variable
    output_path = args.output
    bbox = parse_bbox(args.bbox) if args.bbox else None

    if not os.path.isfile(input_path):
        print(f"ERROR: File '{input_path}' not found.", file=sys.stderr)
        return 1

    try:
        with Dataset(input_path, "r") as ds:
            if variable not in ds.variables:
                print(f"ERROR: Variable '{variable}' not found.", file=sys.stderr)
                return 1

            var = ds.variables[variable]
            data = var[:]

            # Get coordinates
            lats = None
            lons = None
            for coord_name in ["lat", "latitude", "y"]:
                if coord_name in ds.variables:
                    lats = ds.variables[coord_name][:]
                    break
            for coord_name in ["lon", "longitude", "x"]:
                if coord_name in ds.variables:
                    lons = ds.variables[coord_name][:]
                    break

            if bbox and lats is not None and lons is not None:
                minlon, minlat, maxlon, maxlat = bbox
                if lats.ndim == 1 and lons.ndim == 1:
                    lat_idx = np.where((lats >= minlat) & (lats <= maxlat))[0]
                    lon_idx = np.where((lons >= minlon) & (lons <= maxlon))[0]
                    if len(lat_idx) == 0 or len(lon_idx) == 0:
                        print("ERROR: No data within the specified bbox.", file=sys.stderr)
                        return 1
                    data = data[..., lat_idx[0]:lat_idx[-1]+1, lon_idx[0]:lon_idx[-1]+1]
                    lats = lats[lat_idx[0]:lat_idx[-1]+1]
                    lons = lons[lon_idx[0]:lon_idx[-1]+1]

            # Ensure 2D
            while data.ndim > 2:
                data = data[0]
            if data.ndim < 2:
                print(f"ERROR: Variable has {data.ndim} dimensions. Need at least 2D.", file=sys.stderr)
                return 1

            # Write GeoTIFF
            if lats is not None and lons is not None:
                transform = from_bounds(float(lons.min()), float(lats.min()),
                                        float(lons.max()), float(lats.max()),
                                        data.shape[1], data.shape[0])
            else:
                transform = rasterio.transform.from_origin(0, 0, 1, 1)

            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            with rasterio.open(
                output_path, "w", driver="GTiff",
                height=data.shape[0], width=data.shape[1], count=1,
                dtype=data.dtype, crs="EPSG:4326", transform=transform,
            ) as dst:
                dst.write(data, 1)

            print(f"Wrote subset to {output_path} ({data.shape[1]}x{data.shape[0]})")
            return 0

    except Exception as e:
        print(f"ERROR: Subset failed: {e}", file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="netcdf-toolkit",
        description="Convert, extract, subset, and inspect NetCDF/HDF files.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommand")

    # info
    p_info = subparsers.add_parser("info", help="Show file metadata")
    p_info.add_argument("--input", required=True, help="Input file path")
    p_info.add_argument("--json", action="store_true", help="Output as JSON")

    # convert
    p_convert = subparsers.add_parser("convert", help="Convert variable to GeoTIFF")
    p_convert.add_argument("--input", required=True, help="Input file path")
    p_convert.add_argument("--variable", required=True, help="Variable name")
    p_convert.add_argument("--output", required=True, help="Output GeoTIFF path")
    p_convert.add_argument("--time-index", type=int, default=0, help="Time step index (default 0)")

    # extract
    p_extract = subparsers.add_parser("extract", help="Extract variables")
    p_extract.add_argument("--input", required=True, help="Input file path")
    p_extract.add_argument("--variables", required=True, help="Comma-separated variable names")
    p_extract.add_argument("--output", required=True, help="Output NetCDF path")

    # subset
    p_subset = subparsers.add_parser("subset", help="Spatial/temporal subset")
    p_subset.add_argument("--input", required=True, help="Input file path")
    p_subset.add_argument("--variable", required=True, help="Variable name")
    p_subset.add_argument("--bbox", help="minlon,minlat,maxlon,maxlat")
    p_subset.add_argument("--start", help="Start date (YYYY-MM-DD)")
    p_subset.add_argument("--end", help="End date (YYYY-MM-DD)")
    p_subset.add_argument("--output", required=True, help="Output file path")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    commands = {
        "info": cmd_info,
        "convert": cmd_convert,
        "extract": cmd_extract,
        "subset": cmd_subset,
    }
    handler = commands.get(args.command)
    if handler:
        return handler(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
