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
import csv
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


def _compute_stats(data) -> Dict[str, float]:
    """Compute summary statistics for a 2D numpy array (nodata-aware)."""
    if hasattr(data, "filled"):
        # masked array: drop mask
        flat = data.compressed() if hasattr(data, "compressed") else data.filled(np.nan).ravel()
    else:
        flat = np.asarray(data).ravel()
    flat = flat[np.isfinite(flat)] if hasattr(np, "isfinite") else flat
    if flat.size == 0:
        return {"count": 0, "min": None, "max": None, "mean": None, "std": None}
    return {
        "count": int(flat.size),
        "min": float(np.min(flat)),
        "max": float(np.max(flat)),
        "mean": float(np.mean(flat)),
        "std": float(np.std(flat)),
    }


def write_alt_format(
    fmt: str,
    output_path: str,
    data,
    bounds: Tuple[float, float, float, float],
    *,
    variable: str,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Write raster data as GeoJSON polygon (with stats) or CSV stats file.

    Parameters
    ----------
    fmt : str
        One of "geojson" or "csv".
    output_path : str
        Destination path (the .tif extension is replaced with .geojson / .csv
        when the caller did not already provide the new extension).
    data : ndarray
        2D array of pixel values.
    bounds : tuple
        (min_lon, min_lat, max_lon, max_lat) in WGS84.
    variable : str
        Variable name (used in the GeoJSON properties and CSV header).
    extra : dict, optional
        Extra properties to include in the GeoJSON Feature.
    """
    if fmt not in ("geojson", "csv"):
        return
    # Decide final path: replace .tif with new extension if not already set
    base, _ = os.path.splitext(output_path)
    new_ext = ".geojson" if fmt == "geojson" else ".csv"
    final_path = output_path if output_path.lower().endswith(new_ext) else base + new_ext
    os.makedirs(os.path.dirname(final_path) or ".", exist_ok=True)
    stats = _compute_stats(data)
    minlon, minlat, maxlon, maxlat = bounds

    if fmt == "geojson":
        polygon = {
            "type": "Polygon",
            "coordinates": [[
                [minlon, minlat],
                [maxlon, minlat],
                [maxlon, maxlat],
                [minlon, maxlat],
                [minlon, minlat],
            ]],
        }
        properties: Dict[str, Any] = {
            "variable": variable,
            "width": int(data.shape[1]),
            "height": int(data.shape[0]),
        }
        properties.update(stats)
        if extra:
            properties.update(extra)
        feature = {
            "type": "Feature",
            "geometry": polygon,
            "properties": properties,
        }
        fc = {
            "type": "FeatureCollection",
            "features": [feature],
        }
        with open(final_path, "w", encoding="utf-8") as f:
            json.dump(fc, f, ensure_ascii=False, indent=2)
        print(f"Wrote {final_path} (GeoJSON, {data.shape[1]}x{data.shape[0]})")
    else:  # csv
        with open(final_path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["variable", "min_lon", "min_lat", "max_lon", "max_lat",
                        "width", "height", "count", "min", "max", "mean", "std"])
            w.writerow([
                variable, minlon, minlat, maxlon, maxlat,
                data.shape[1], data.shape[0],
                stats["count"], stats["min"], stats["max"], stats["mean"], stats["std"],
            ])
        print(f"Wrote {final_path} (CSV stats)")


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
    fmt = getattr(args, "format", "geotiff") or "geotiff"

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
                    minlon, minlat, maxlon, maxlat = 0.0, 0.0, float(data.shape[1]), float(data.shape[0])
            else:
                transform = rasterio.transform.from_origin(0, 0, 1, 1)
                minlon, minlat, maxlon, maxlat = 0.0, 0.0, float(data.shape[1]), float(data.shape[0])

            # Write GeoTIFF (default) or alternative format
            if fmt == "geotiff":
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
            else:
                write_alt_format(
                    fmt, output_path, data,
                    (minlon, minlat, maxlon, maxlat),
                    variable=variable,
                    extra={"time_index": time_index, "source": input_path},
                )
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
    fmt = getattr(args, "format", "geotiff") or "geotiff"

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

            # Compute bounds and transform
            if lats is not None and lons is not None:
                minlon, maxlon = float(lons.min()), float(lons.max())
                minlat, maxlat = float(lats.min()), float(lats.max())
                transform = from_bounds(minlon, minlat, maxlon, maxlat,
                                        data.shape[1], data.shape[0])
            else:
                transform = rasterio.transform.from_origin(0, 0, 1, 1)
                minlon, minlat, maxlon, maxlat = 0.0, 0.0, float(data.shape[1]), float(data.shape[0])

            if fmt == "geotiff":
                os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
                with rasterio.open(
                    output_path, "w", driver="GTiff",
                    height=data.shape[0], width=data.shape[1], count=1,
                    dtype=data.dtype, crs="EPSG:4326", transform=transform,
                ) as dst:
                    dst.write(data, 1)

                print(f"Wrote subset to {output_path} ({data.shape[1]}x{data.shape[0]})")
                return 0
            else:
                extra = {"source": input_path}
                if args.bbox:
                    extra["requested_bbox"] = bbox
                if getattr(args, "start", None):
                    extra["start"] = args.start
                if getattr(args, "end", None):
                    extra["end"] = args.end
                write_alt_format(
                    fmt, output_path, data,
                    (minlon, minlat, maxlon, maxlat),
                    variable=variable, extra=extra,
                )
                return 0

    except Exception as e:
        print(f"ERROR: Subset failed: {e}", file=sys.stderr)
        return 1


def cmd_from_place(args) -> int:
    """One-line: resolve --place via geoskill_core.aoi + fetch NetCDF + subset + convert.

    [PHASE 1+ 2026-07-26 REFACTOR]
    Step 1: _geoskill_core.aoi.resolve_place(place) → bbox
    Step 2: subprocess 调 era5-download / gpm-download 拉 NetCDF
    Step 3: 调本 skill cmd_subset 或 cmd_convert
    """
    import os as _os
    import sys as _sys
    import subprocess as _sp

    skill_dir = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    gk_dir = _os.path.join(skill_dir, "_geoskill_core")
    if not _os.path.isdir(gk_dir):
        print("ERROR: _geoskill_core not vendored. Run vendor.py.", file=sys.stderr)
        return 3
    if skill_dir not in _sys.path:
        _sys.path.insert(0, skill_dir)
    try:
        from _geoskill_core import aoi as _aoi
    except Exception as _e:
        print(f"ERROR: failed to import _geoskill_core.aoi: {_e}", file=sys.stderr)
        return 3
    try:
        m = _aoi.resolve_place(args.place, allow_nominatim=not args.no_nominatim, use_cache=False)
    except Exception as _e:
        print(f"ERROR: failed to resolve --place={args.place!r}: {_e}", file=sys.stderr)
        return 5
    bbox = m.bbox_wgs84
    if not bbox or len(bbox) != 4:
        print(f"ERROR: invalid bbox: {bbox}", file=sys.stderr)
        return 5
    print(f"[from-place] resolved {args.place!r} → bbox={bbox} (resolver={m.resolver})",
          file=sys.stderr)
    # Step 2: 选 fetch skill
    parent = _os.path.dirname(skill_dir)
    dataset = (args.dataset or "era5").lower()
    if "gpm" in dataset:
        fetch_dir = _os.path.join(parent, "gpm-download")
        fetch_script = _os.path.join(fetch_dir, "gpm_download.py")
        if not _os.path.isfile(fetch_script):
            fetch_script = _os.path.join(fetch_dir, "scripts", "gpm_download.py")
    else:
        fetch_dir = _os.path.join(parent, "era5-download")
        fetch_script = _os.path.join(fetch_dir, "era5-download.py")
        if not _os.path.isfile(fetch_script):
            fetch_script = _os.path.join(fetch_dir, "scripts", "era5_download.py")
    if not _os.path.isfile(fetch_script):
        print(f"ERROR: fetch script not found: {fetch_script}", file=sys.stderr)
        return 3
    out_dir = _os.path.dirname(args.output) or "."
    cache_dir = _os.path.join(out_dir, ".from_place_cache")
    _os.makedirs(cache_dir, exist_ok=True)
    start = getattr(args, "start_date", "2024-01-01")
    end = getattr(args, "end_date", "2024-01-31")
    cmd = [
        _sys.executable, fetch_script,
        "--bbox", str(bbox[0]), str(bbox[1]), str(bbox[2]), str(bbox[3]),
        "--start", start,
        "--end", end,
        "--output-dir", cache_dir,
    ]
    if dataset and dataset != "era5":
        cmd += ["--dataset", dataset]
    print(f"[from-place] invoking: {' '.join(cmd)}", file=sys.stderr)
    try:
        r = _sp.run(cmd, capture_output=True, text=True, timeout=600)
    except _sp.TimeoutExpired:
        print("ERROR: fetch timeout (600s)", file=sys.stderr)
        return 4
    except Exception as _e:
        print(f"ERROR: fetch failed: {_e}", file=sys.stderr)
        return 7
    if r.returncode != 0:
        print(f"ERROR: fetch exit {r.returncode}:\n{r.stderr[-500:]}", file=sys.stderr)
        return r.returncode
    nc_files = []
    for root, _, files in _os.walk(cache_dir):
        for f in files:
            if f.endswith(".nc") and not f.endswith(".part"):
                nc_files.append(_os.path.join(root, f))
    if not nc_files:
        print(f"ERROR: no .nc produced in {cache_dir}", file=sys.stderr)
        return 5
    # Step 3: 调本 skill convert
    convert_args = argparse.Namespace(
        inputs=nc_files, output=args.output,
        var=getattr(args, "var", None),
        bbox=bbox,
        variable=getattr(args, "var", None) or "data",
        input=nc_files[0] if nc_files else "",
        time_index=getattr(args, "time_index", 0),
        format=getattr(args, "format", "geotiff"),
    )
    return cmd_convert(convert_args)

    _shared_path = _os.path.join(
        _os.path.dirname(_os.path.abspath(__file__)), "..", "..", "_shared", "from_stac.py"
    )
    _shared_path = _os.path.abspath(_shared_path)
    if not _os.path.exists(_shared_path):
        print(f"ERROR: shared helper not found at {_shared_path}", file=sys.stderr)
        return 2
    spec = importlib.util.spec_from_file_location("from_stac", _shared_path)
    fs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fs)
    if not fs.is_available():
        print("ERROR: requires: pip install planetary-computer pystac-client rasterio xarray",
              file=sys.stderr)
        return 2

    try:
        meta = fs.fetch_scenes(
            place=args.place,
            start=args.start, end=args.end,
            dataset=args.dataset,
            bands=[args.asset],
            max_cloud=100.0,
            limit=1,
            output_dir=args.cache_dir,
            no_nominatim=args.no_nominatim,
            buffer_deg=args.buffer_deg,
            quiet=False,
        )
    except Exception as e:
        print(f"ERROR: fetch_scenes failed: {e}", file=sys.stderr)
        return 1

    nc_path = meta["scenes"][0]["asset_paths"].get(args.asset)
    if not nc_path or not _os.path.exists(nc_path):
        print(f"ERROR: asset {args.asset!r} not found in fetched scene", file=sys.stderr)
        return 1

    # Subset to bbox and convert
    sub_args = argparse.Namespace(
        input=nc_path, variable=args.variable, bbox=",".join(f"{x:.4f}" for x in meta["bbox"]),
        start=args.start, end=args.end, output=args.output,
    )
    print(f"[from-place] subsetting to bbox {meta['bbox']} ...", file=sys.stderr)
    rc = cmd_subset(sub_args)
    if rc != 0:
        return rc

    if args.qa:
        qa = {
            "skill": "netcdf-toolkit",
            "version": "0.2.0",
            "command": "from-place",
            "place": meta["place"],
            "bbox": meta["bbox"],
            "dataset": args.dataset,
            "asset": args.asset,
            "variable": args.variable,
            "start": args.start, "end": args.end,
            "nc_source": nc_path,
            "output": args.output,
        }
        qa_path = args.output + ".qa.json"
        with open(qa_path, "w", encoding="utf-8") as f:
            json.dump(qa, f, ensure_ascii=False, indent=2)
        print(f"[from-place] QA written to {qa_path}", file=sys.stderr)
    return 0


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
    p_convert.add_argument("--format", choices=["geotiff", "geojson", "csv"], default="geotiff",
                           help="Output format (default: geotiff). geojson/csv write a polygon + stats file "
                                "next to --output (replacing the extension).")

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
    p_subset.add_argument("--format", choices=["geotiff", "geojson", "csv"], default="geotiff",
                          help="Output format (default: geotiff). geojson/csv write a polygon + stats file "
                               "next to --output (replacing the extension).")

    # from-place (v0.2.0): 拉 PC 的 NetCDF + 转 GeoTIFF
    p_fp = subparsers.add_parser(
        "from-place",
        help="One-line: --place + --variable → fetch a PC NetCDF asset + subset to AOI + write GeoTIFF. "
             "Common dataset: era5-pds, nasa-nex-gddp-cmip6, daymet-daily-hi, etc.",
    )
    p_fp.add_argument("--place", required=True, help="行政区名 (中文/English) → bbox")
    p_fp.add_argument("--dataset", required=True,
                     help="PC STAC collection id, e.g. era5-pds, nasa-nex-gddp-cmip6")
    p_fp.add_argument("--asset", required=True,
                     help="STAC asset key (NetCDF .nc), e.g. air_temperature_at_2_metres")
    p_fp.add_argument("--variable", required=True,
                     help="NetCDF variable to extract (e.g. t2m, prate)")
    p_fp.add_argument("--start", required=True, help="开始日期 YYYY-MM-DD")
    p_fp.add_argument("--end", required=True, help="结束日期 YYYY-MM-DD")
    p_fp.add_argument("--buffer-deg", type=float, default=0.3)
    p_fp.add_argument("--cache-dir", default="./netcdf_cache")
    p_fp.add_argument("--no-nominatim", action="store_true")
    p_fp.add_argument("--time-index", type=int, default=-1,
                     help="时间索引 (-1 = last, 0 = first; default last)")
    p_fp.add_argument("--output", required=True, help="Output GeoTIFF path")
    p_fp.add_argument("--format", choices=["geotiff", "geojson", "csv"], default="geotiff",
                     help="Output format (default: geotiff). geojson/csv write a polygon + stats "
                          "file next to --output (replacing the extension).")
    p_fp.add_argument("--qa", action="store_true")
    p_fp.set_defaults(func=None)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "from-place":
        return cmd_from_place(args)

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
