---
name: netcdf-toolkit
description: 'Convert NetCDF/HDF files to GeoTIFF, extract variables, subset by time description: 'Convert NetCDF/HDF files to GeoTIFF, extract variables, subset by time and spatial  bbox, and inspect file metadata. All processing is local — no data is uploaded.  '
---

# NetCDF Toolkit

Process NetCDF and HDF files locally: convert to GeoTIFF, extract variables,
subset by time range and spatial bounding box, and inspect file metadata.

## Features

- Show file metadata (variables, dimensions, attributes)
- Convert any variable to GeoTIFF
- Extract specific variables from multi-variable files
- Subset by time range and spatial bbox
- Batch-friendly design

## Requirements

```bash
pip install netCDF4 rasterio numpy
```

## Usage

```bash
# Show file info
python scripts\netcdf-toolkit.py info --input data.nc

# Convert a variable to GeoTIFF
python scripts\netcdf-toolkit.py convert --input data.nc --variable temperature --output temp.tif

# Extract variables
python scripts\netcdf-toolkit.py extract --input data.nc --variables temp,pressure --output subset.nc

# Subset spatially and temporally
python scripts\netcdf-toolkit.py subset --input data.nc --variable temp --bbox 73,18,135,54 --output subset.tif
```

## Installation

```bash
pip install netCDF4 rasterio numpy
# Or: pip install -r scripts/requirements.txt
```

## Parameters

### `info`
| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--input` | Yes | — | Input NetCDF/HDF file path |
| `--json` | No | false | Output as JSON |

### `convert`
| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--input` | Yes | — | Input file path |
| `--variable` | Yes | — | Variable name to convert |
| `--output` | Yes | — | Output GeoTIFF path |
| `--time-index` | No | 0 | Time step index |

### `extract`
| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--input` | Yes | — | Input file path |
| `--variables` | Yes | — | Comma-separated variable names |
| `--output` | Yes | — | Output NetCDF path |

### `subset`
| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--input` | Yes | — | Input file path |
| `--variable` | Yes | — | Variable name |
| `--bbox` | No | — | minlon,minlat,maxlon,maxlat |
| `--start` | No | — | Start date (YYYY-MM-DD) |
| `--end` | No | — | End date (YYYY-MM-DD) |
| `--output` | Yes | — | Output file path |

## Data Source

- **Input**: Local NetCDF/HDF files (no download)
- **Output**: GeoTIFF, NetCDF
- **Processing**: 100% local

### Batch Processing

Loop over multiple files with a shell script:

```bash
# Convert all NetCDF files in a directory
for f in data/*.nc; do
  python scripts\netcdf-toolkit.py convert \
    --input "$f" \
    --variable temperature \
    --output "output/$(basename "$f" .nc).tif"
done
```

### CRS Handling

- Source CRS is preserved in output GeoTIFF (embedded in GeoTIFF tags)
- If source CRS is missing, assumes WGS84 (EPSG:4326)
- Use `--crs EPSG:XXXX` to override output CRS
- Reprojection is not performed; use `gdalwarp` for reprojection

### Output Data Type

- Default: preserves source data type (e.g., float32 stays float32)
- Specify with `--dtype`: `float32`, `float64`, `int16`, `int32`
- Use `--dtype int16` to reduce file size (with appropriate scaling)

### Nodata Handling

- Source nodata value is preserved in output
- Use `--nodata VALUE` to set a custom nodata value
- If source has no nodata attribute, output will also lack one

### Memory / Large File Guidance

- For files > 2GB, use `--chunk` to process in tiles
- Chunk size specified in pixels: `--chunk 1024` processes 1024×1024 tiles
- Use `info` command first to assess file size and dimensions
- Close other memory-intensive applications when processing large files

### HDF Subdatasets

- HDF5 files may contain multiple subdatasets
- Use `info` to list available subdatasets
- Access subdatasets with `--subdataset PATH` (e.g., `/science/grids/data/temperature`)
- Common in NASA HDF-EOS (MODIS, AIRS) products

### Example `info` Output

```
File: data.nc
Dimensions: time(365), lat(721), lon(1440)
Variables:
  temperature (float32): K, dims=(time, lat, lon)
  pressure (float32): Pa, dims=(time, lat, lon)
CRS: EPSG:4326
Bounds: -180.0, -90.0, 180.0, 90.0
```

### Time Format

- Time values follow ISO 8601: `YYYY-MM-DDTHH:MM:SS`
- Time units attribute: `days since 1900-01-01` or `seconds since 1970-01-01`
- Use `--start` and `--end` with `YYYY-MM-DD` format for subsetting

## Visualization

- Quick plot with `rasterio.plot.show()`: single-band visualization
- Multi-panel time series: use `matplotlib` subplots for different time steps
- Use `matplotlib` colormaps: `cmap='viridis'` for temperature, `cmap='Blues'` for precipitation
- Animate time series with `matplotlib.animation` or `xarray`

## Troubleshooting

| Error | Cause | Solution |
|-------|-------|----------|
| `ConnectionError` | Network issue | Check internet, retry |
| `HTTP 429` | Rate limit | Wait 60s, retry |
| `ValueError` | Invalid input | Check parameter format |
| Empty output | No data | Try different parameters |
| `ModuleNotFoundError` | Missing dep | Run pip install |
| `MemoryError` | File too large | Use `--chunk` for tiled processing |
| `KeyError` | Variable not found | Check variable name with `info` |
| HDF subdataset error | Wrong path | Use `info` to list subdatasets |

## Citation

If you use this tool in your research, please cite the input data source (e.g., NASA, NOAA, ECMWF) and acknowledge this tool:

```bibtex
@software{netcdf_toolkit_2024,
  author = {ruiduobao},
  title = {NetCDF Toolkit},
  year = {2024},
  note = {NetCDF/HDF to GeoTIFF conversion and subsetting}
}
```

---

## Advanced Usage

### Batch Convert Multiple Files
```bash
# Convert all NetCDF files in a directory to GeoTIFF
for f in data/*.nc; do
  python scripts\netcdf-toolkit.py convert     --input "$f" --variable Band1 --output "${f%.nc}.tif"
done
```

### CI/CD Integration (GitHub Actions)
```yaml
# .github/workflows/convert-netcdf.yml
name: Convert NetCDF Batch
on:
  push:
    paths: ['data/*.nc']
jobs:
  convert:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install numpy h5netcdf rasterio
      - run: |
          for f in data/*.nc; do
            python scripts\netcdf-toolkit.py convert \
              --input "$f" --variable Band1 --output "${f%.nc}.tif"
          done
```

### PostgreSQL/PostGIS Raster Import
```bash
python scripts\netcdf-toolkit.py convert   --input temperature.nc --variable t2m --output t2m.tif

raster2pgsql -s 4326 -I -C t2m.tif public.t2m_raster | psql -d gis_db
```

### Performance Tips
- Use `--subset` with `--bbox` to extract only the area of interest (reduces memory)
- For large files, use `--sequential` mode to limit memory usage
- HDF4 files require `h5netcdf` engine; check availability with `python scripts\netcdf-toolkit.py info --input file.hdf`

---

## 中文说明

在本地处理 NetCDF 和 HDF 文件：转换为 GeoTIFF、提取变量、按时间和空间子集、查看文件元数据。

### 功能

- 查看文件元数据（变量、维度、属性）
- 将任意变量转换为 GeoTIFF
- 从多变量文件中提取指定变量
- 按时间范围和空间边界子集
- 支持批量处理

### 依赖

```bash
pip install netCDF4 rasterio numpy
```

### 使用方法

```bash
# 查看文件信息
python scripts\netcdf-toolkit.py info --input data.nc

# 转换变量为 GeoTIFF
python scripts\netcdf-toolkit.py convert --input data.nc --variable temperature --output temp.tif

# 提取变量
python scripts\netcdf-toolkit.py extract --input data.nc --variables temp,pressure --output subset.nc

# 空间和时间子集
python scripts\netcdf-toolkit.py subset --input data.nc --variable temp --bbox 73,18,135,54 --output subset.tif
```

### 数据来源

- **输入**: 本地 NetCDF/HDF 文件（无下载）
- **输出**: GeoTIFF, NetCDF
- **处理**: 完全本地

### 批量处理

使用 shell 脚本循环处理多个文件:

```bash
# 转换目录中所有 NetCDF 文件
for f in data/*.nc; do
  python scripts\netcdf-toolkit.py convert \
    --input "$f" \
    --variable temperature \
    --output "output/$(basename "$f" .nc).tif"
done
```

### 坐标系处理

- 输出 GeoTIFF 中保留源 CRS（嵌入 GeoTIFF 标签）
- 如果源 CRS 缺失，假定为 WGS84 (EPSG:4326)
- 使用 `--crs EPSG:XXXX` 覆盖输出 CRS
- 不执行重投影；使用 `gdalwarp` 进行重投影

### 输出数据类型

- 默认: 保留源数据类型（如 float32 保持 float32）
- 使用 `--dtype` 指定: `float32`, `float64`, `int16`, `int32`
- 使用 `--dtype int16` 减小文件大小（需适当缩放）

### 无数据值处理

- 输出中保留源 nodata 值
- 使用 `--nodata VALUE` 设置自定义 nodata 值
- 如果源没有 nodata 属性，输出也将缺少该属性

### 内存/大文件指南

- 对于 > 2GB 的文件，使用 `--chunk` 分块处理
- 块大小以像素指定: `--chunk 1024` 处理 1024×1024 瓦片
- 先用 `info` 命令评估文件大小和维度
- 处理大文件时关闭其他内存密集型应用程序

### HDF 子数据集

- HDF5 文件可能包含多个子数据集
- 使用 `info` 列出可用子数据集
- 使用 `--subdataset PATH` 访问子数据集（如 `/science/grids/data/temperature`）
- 常见于 NASA HDF-EOS (MODIS, AIRS) 产品

### `info` 输出示例

```
File: data.nc
Dimensions: time(365), lat(721), lon(1440)
Variables:
  temperature (float32): K, dims=(time, lat, lon)
  pressure (float32): Pa, dims=(time, lat, lon)
CRS: EPSG:4326
Bounds: -180.0, -90.0, 180.0, 90.0
```

### 时间格式

- 时间值遵循 ISO 8601: `YYYY-MM-DDTHH:MM:SS`
- 时间单位属性: `days since 1900-01-01` 或 `seconds since 1970-01-01`
- 子集操作使用 `--start` 和 `--end`，格式为 `YYYY-MM-DD`

### 可视化

- 使用 `rasterio.plot.show()` 快速绘图: 单波段可视化
- 多面板时间序列: 使用 `matplotlib` subplots 显示不同时间步
- 使用 `matplotlib` 色标: 温度用 `cmap='viridis'`，降水用 `cmap='Blues'`
- 使用 `matplotlib.animation` 或 `xarray` 制作时间序列动画

### 故障排除

| 错误 | 原因 | 解决方案 |
|------|------|----------|
| `ConnectionError` | 网络问题 | 检查网络，重试 |
| `HTTP 429` | 速率限制 | 等待 60 秒后重试 |
| `ValueError` | 无效输入 | 检查参数格式 |
| 空输出 | 无数据 | 尝试不同参数 |
| `ModuleNotFoundError` | 缺少依赖 | 运行 pip install |
| `MemoryError` | 文件过大 | 使用 `--chunk` 分块处理 |
| `KeyError` | 变量未找到 | 使用 `info` 检查变量名 |
| HDF 子数据集错误 | 路径错误 | 使用 `info` 列出子数据集 |
