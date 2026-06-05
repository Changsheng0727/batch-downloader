# Batch Imagery Downloader

[English](README.md) | [中文](README.zh-CN.md)

本项目用于批量下载 Esri Wayback World Imagery 瓦片，将瓦片拼接成 GeoTIFF 栅格，并使用 ArcGIS/ArcPy 按行政区边界进行裁剪。

当前示例使用甘肃省数据，因为这是项目最早落地使用的数据集；但工作流并不局限于甘肃。只要你准备好下面这些数据，就可以用于任意省份、城市、县区集合或自定义区域：

- 区域估算 CSV，包含瓦片范围
- 用于裁剪的边界要素类或 Shapefile
- ArcGIS Desktop/ArcPy Python 环境
- 输出目录和工作目录

## 功能

- 从估算 CSV 读取瓦片范围
- 支持按区域 ID 选择任务，例如 `--areas 1,11,18` 或 `--areas 1-10`
- 自动把较大的区域拆成内部块进行下载和裁剪
- 重跑时复用已经完成的内部裁剪块
- 将多个内部块合并为一个最终 GeoTIFF
- 并发下载瓦片，并使用本地缓存
- 输出状态 CSV，记录完成、跳过和失败的区域
- 甘肃省只是示例数据，核心流程可以复用于其他省份或区域

## 项目结构

```text
batch-downloader/
  src/gansu_downloader/
    arcgis.py      # ArcGIS/ArcPy 裁剪、镶嵌和 PRJ 生成
    batch.py       # 批量下载工作流
    cli.py         # 命令行入口
    estimates.py   # 估算 CSV 读取和分块规划
    status.py      # 状态 CSV 写入
    tiles.py       # 坐标转换、瓦片下载和影像拼接
  configs/
    gansu.example.json
  scripts/
    run_gansu_example.ps1
```

说明：模块名和示例配置名中仍保留 `gansu`，是因为项目最初从甘肃数据集整理而来；下载逻辑本身是通用的。

## 环境

- Python 3.10+，用于主下载程序
- ArcGIS Desktop 10.x Python 2.7，或其他可用的 ArcPy Python 环境，用于裁剪和镶嵌
- Python 依赖：`requests`、`Pillow`

安装依赖：

```powershell
cd path\to\batch-downloader
python -m pip install -r requirements.txt
```

## 配置路径

本项目不内置固定本机路径。运行前请复制示例配置，并修改其中所有 `CHANGE_ME` 路径，尤其是 `arcgis_python`。

```powershell
copy configs\gansu.example.json configs\gansu.local.json
notepad configs\gansu.local.json
```

示例配置字段：

```json
{
  "estimate_csv": "CHANGE_ME/path/to/region_estimate.csv",
  "out_dir": "CHANGE_ME/path/to/final_geotiffs",
  "work_dir": "CHANGE_ME/path/to/work_dir",
  "reference_dir": "CHANGE_ME/path/to/reference_dir_with_web_mercator_prj",
  "arcgis_python": "CHANGE_ME/path/to/ArcGIS/python.exe",
  "resolution": 5.0,
  "wayback_id": "58924",
  "workers": 16,
  "max_tiles_per_chunk": 2000,
  "order": "largest-first",
  "status_csv_name": "download_status.csv"
}
```

如果要处理其他省份或区域，创建自己的本地配置文件，保留相同字段，并把路径指向你的数据即可。`reference_dir` 只需要包含 `web_mercator_aux_sphere.prj`，它不绑定任何省份。

## 运行

只预览计划，不下载：

```powershell
python -m gansu_downloader.cli --config configs\gansu.local.json --dry-run
```

下载配置中的所有区域：

```powershell
python -m gansu_downloader.cli --config configs\gansu.local.json
```

补跑或只运行指定区域 ID：

```powershell
python -m gansu_downloader.cli --config configs\gansu.local.json --areas 71,1,11,18,45,51,75
```

## 输出

最终 GeoTIFF 输出：

```text
path\to\final_geotiffs/
  region_001_5m_clipped.tif
  region_002_5m_clipped.tif
  download_status.csv
```

内部工作目录：

```text
path\to\work_dir/
  raw/
  region_001/
  region_001_part_0001_clipped.tif
```

实际文件前缀取决于估算 CSV 中的 `ascii` 字段。

## 注意事项

下载结果、瓦片缓存、ArcGIS 工作空间和日志通常很大。不要把生成影像或本地数据提交到 Git。仓库中的 `.gitignore` 已排除常见栅格、GIS、缓存、日志和输出文件。

## 反馈与联系

如果使用过程中遇到问题，欢迎在 GitHub Issues 中提出，也可以通过下面的邮箱联系我：

`2821452633@qq.com`
