# NetCDF Toolkit Skill - Development Doc

## Purpose
Convert NetCDF/HDF files to GeoTIFF, extract variables, subset by time/space, show metadata.

## Libraries
- `netCDF4` or `h5netcdf` for reading NetCDF/HDF
- `rasterio` for GeoTIFF output
- `numpy` for array operations

## CLI Design
```
netcdf-toolkit info --input data.nc
netcdf-toolkit convert --input data.nc --variable temperature --output temp.tif
netcdf-toolkit extract --input data.nc --variables temp,pressure --output subset.nc
netcdf-toolkit subset --input data.nc --variable temp --bbox 73,18,135,54 --start 2020-01-01 --end 2020-12-31
```

### Subcommands
- `info`: show file metadata
  - `--input`: input file path
  - `--json`: output as JSON
- `convert`: convert to GeoTIFF
  - `--input`: input file
  - `--variable`: variable name
  - `--output`: output GeoTIFF path
  - `--time-index`: time step index (default 0)
- `extract`: extract variables
  - `--input`: input file
  - `--variables`: comma-separated variable names
  - `--output`: output NetCDF path
- `subset`: spatial/temporal subset
  - `--input`: input file
  - `--variable`: variable name
  - `--bbox`: minlon,minlat,maxlon,maxlat
  - `--start`: start date
  - `--end`: end date
  - `--output`: output path

## Privacy
- All processing is local. No data sent anywhere.

## Error Handling
- Graceful handling of missing libraries
- Clear install instructions
- Validate bbox ranges
