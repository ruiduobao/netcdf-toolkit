# NetCDF Toolkit

Process NetCDF and HDF files locally: convert to GeoTIFF, extract variables,
subset by time and spatial bbox, and inspect file metadata.

## Install

### ClawHub
```bash
clawhub install netcdf-toolkit
```

### Manual
```bash
git clone https://github.com/ruiduobao/netcdf-toolkit.git
cd netcdf-toolkit
pip install netCDF4 rasterio numpy
```

### Claude Code / skills.sh
```bash
claude skills install netcdf-toolkit
```

## Quick Start

```bash
# Show file info
python scripts/netcdf-toolkit.py info --input data.nc

# Convert to GeoTIFF
python scripts/netcdf-toolkit.py convert --input data.nc --variable temperature --output temp.tif

# Subset by bbox
python scripts/netcdf-toolkit.py subset --input data.nc --variable temp --bbox 73,18,135,54 --output subset.tif
```

## Data Source

- **Input**: Local NetCDF/HDF files
- **Processing**: 100% local, no data uploaded

---

# NetCDF 数据工具包

在本地处理 NetCDF 和 HDF 文件：转换为 GeoTIFF、提取变量、按时间和空间子集、查看元数据。

## 安装

### ClawHub
```bash
clawhub install netcdf-toolkit
```

### 手动安装
```bash
git clone https://github.com/ruiduobao/netcdf-toolkit.git
cd netcdf-toolkit
pip install netCDF4 rasterio numpy
```

### Claude Code / skills.sh
```bash
claude skills install netcdf-toolkit
```

## 快速开始

```bash
# 查看文件信息
python scripts/netcdf-toolkit.py info --input data.nc

# 转换为 GeoTIFF
python scripts/netcdf-toolkit.py convert --input data.nc --variable temperature --output temp.tif

# 按边界子集
python scripts/netcdf-toolkit.py subset --input data.nc --variable temp --bbox 73,18,135,54 --output subset.tif
```

## 数据来源

- **输入**: 本地 NetCDF/HDF 文件
- **处理**: 完全本地，无数据上传
