# Batch Imagery Downloader

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![ArcGIS](https://img.shields.io/badge/ArcGIS-Desktop%2010.x-2C7AC3)](https://www.esri.com/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D4?logo=windows&logoColor=white)](https://www.microsoft.com/windows/)

[English](README.md) | [中文](README.zh-CN.md)

这是一个面向批量任务的影像下载工具：从 Esri Wayback World Imagery 下载瓦片，拼接成 GeoTIFF，再使用 ArcGIS/ArcPy 按行政边界裁剪成最终结果。

仓库里的示例数据来自甘肃县区项目，因为这是最早落地的一套生产流程；但工具本身并不局限于甘肃。当前版本既可以直接复用现成的估算 CSV，也可以只提供一个面要素边界数据源，让程序自动生成估算 CSV。

- 支持大区域分块下载与断点续跑
- 支持并发抓取、连接复用和本地瓦片缓存
- 支持 ArcGIS 裁剪与最终输出安全替换
- 支持 JSON 配置，方便固定化批处理任务

## 目录

- [项目定位](#项目定位)
- [工作流程](#工作流程)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [命令行用法](#命令行用法)
- [输出结构](#输出结构)
- [项目结构](#项目结构)
- [运行注意事项](#运行注意事项)
- [常见问题](#常见问题)

## 项目定位

这个项目适合长时间运行、数据量较大的遥感下载任务，而不是一次性的小脚本。

当前版本相较于早期脚本，已经补上了这些更适合生产使用的能力：

- 自动把大区域拆成内部块，降低单次任务失败风险
- 不加 `--redo` 时，重跑会自动复用已经完成的裁剪块
- 下载线程复用 HTTP 会话，适合大批量瓦片抓取
- 下载到的瓦片现在会保留在 `work_dir\tile_cache` 这个共享缓存里，重跑任务或相邻区域下载时会自动复用
- 最终 GeoTIFF 只有在成功合并后才会替换旧结果，减少重跑时误覆盖成品的风险
- ArcGIS 中间裁剪过程关闭不必要的金字塔和统计信息，减少额外开销
- 现在可以直接用一个边界要素类驱动整套流程：自动生成估算 CSV、自动补默认 `work_dir`，并在常见 Windows 安装位置自动探测 ArcGIS Python

## 工作流程

```text
边界数据源或估算 CSV
  -> 需要时自动生成估算 CSV
  -> 选择区域 ID
  -> 大区域拆分为内部块
  -> 并发下载瓦片并使用本地缓存
  -> 每个块先拼接为原始 TIFF
  -> 使用 ArcGIS 对每个块裁剪
  -> 合并多个块为最终 GeoTIFF
  -> 写出状态 CSV
```

## 快速开始

### 1. 安装依赖

```powershell
cd path\to\batch-downloader
python -m pip install -e .
```

### 2. 准备本地配置

```powershell
copy configs\gansu.example.json configs\gansu.local.json
notepad configs\gansu.local.json
```

至少把 `boundary_source` 和 `out_dir` 改成自己的路径。若 ArcGIS Python 安装在常见位置，命令行通常可以自动识别；像 `PAC`、`NAME`、`ascii` 这类常见边界字段也往往能自动判断，不再必须手填。

### 3. 先做干跑预览

```powershell
python -m gansu_downloader.cli --config configs\gansu.local.json --dry-run
```

### 4. 正式执行批量任务

```powershell
python -m gansu_downloader.cli --config configs\gansu.local.json
```

## 配置说明

示例配置：

```json
{
  "boundary_source": "CHANGE_ME/path/to/county_boundaries.shp",
  "out_dir": "CHANGE_ME/path/to/final_geotiffs",
  "resolution": 5.0,
  "wayback_id": "58924",
  "workers": 12,
  "max_tiles_per_chunk": 2000,
  "order": "largest-first",
  "status_csv_name": "download_status.csv",
  "refresh_estimates": false,
  "redo": false,
  "keep_parts": false,
  "dry_run": false
}
```

关键字段说明：

| 字段 | 是否必填 | 作用 |
| --- | --- | --- |
| `boundary_source` | 是，除非已经提供 `estimate_csv` | 用于自动生成估算 CSV 的面要素类 / Shapefile |
| `estimate_csv` | 是，除非已经提供 `boundary_source` | 已经准备好的估算 CSV，包含区域 ID、瓦片范围、裁剪来源和输出命名字段 |
| `id_field` | 否 | 边界数据中的数值型唯一 ID 字段；省略时会自动识别 |
| `name_field` | 否 | 边界数据中的显示名称字段；省略时会自动识别 |
| `ascii_field` | 否 | 输出文件名前缀字段；省略时会自动识别，不可用时会回退为 `region_001` 这种名字 |
| `out_dir` | 是 | 最终裁剪 GeoTIFF 输出目录 |
| `work_dir` | 否 | 中间块结果、原始拼接结果、共享瓦片缓存，以及自动生成的估算 CSV；默认是 `out_dir\_work` |
| `reference_dir` | 否 | 可选，若提供则应包含 `web_mercator_aux_sphere.prj`；不提供时程序会用 ArcPy 自动生成 |
| `arcgis_python` | 否 | ArcGIS Desktop / ArcPy 的 Python 可执行文件；省略时会尝试在常见 Windows 安装位置自动探测 |
| `resolution` | 否 | 目标分辨率，默认 `5.0` 米/像素 |
| `wayback_id` | 否 | Esri Wayback 影像版本，默认 `58924` |
| `workers` | 否 | 下载并发数，默认 `12` |
| `max_tiles_per_chunk` | 否 | 每个内部块允许的最大瓦片数 |
| `order` | 否 | 处理顺序，可选 `id` 或 `largest-first` |
| `refresh_estimates` | 否 | 运行前强制根据边界数据重新生成估算 CSV |
| `redo` | 否 | 强制重建，即使已有中间结果或最终结果 |
| `keep_parts` | 否 | 保留中间裁剪块，不在最终合并后清理 |
| `dry_run` | 否 | 仅输出计划，不实际下载 |

如果使用 `boundary_source`，自动生成的估算 CSV 会写到 `work_dir\region_estimate.generated.csv`，后续重跑默认会复用，除非加上 `--refresh-estimates`。

## 命令行用法

运行配置里的全部区域：

```powershell
python -m gansu_downloader.cli --config configs\gansu.local.json
```

不手工准备估算 CSV，直接运行：

```powershell
python -m gansu_downloader.cli --boundary-source D:\data\counties.shp --out-dir D:\imagery\out
```

只运行指定区域 ID：

```powershell
python -m gansu_downloader.cli --config configs\gansu.local.json --areas 1,11,18
```

运行一个 ID 范围：

```powershell
python -m gansu_downloader.cli --config configs\gansu.local.json --areas 1-10
```

强制重下某个区域：

```powershell
python -m gansu_downloader.cli --config configs\gansu.local.json --areas 48 --redo
```

运行前刷新自动生成的估算 CSV：

```powershell
python -m gansu_downloader.cli --config configs\gansu.local.json --refresh-estimates
```

## 输出结构

最终输出：

```text
path\to\final_geotiffs\
  region_001_5m_clipped.tif
  region_002_5m_clipped.tif
  download_status.csv
```

工作目录：

```text
path\to\work_dir\
  raw\
  tile_cache\
  region_001_part_0001_clipped.tif
  region_001_part_0002_clipped.tif
```

实际文件前缀由估算 CSV 中的 `ascii` 字段决定；如果该字段缺失或不可用，程序会自动回退为 `region_001`、`region_002` 这样的名字。

## 项目结构

```text
batch-downloader/
  configs/
    gansu.example.json
  scripts/
    run_gansu_example.ps1
  src/gansu_downloader/
    arcgis.py      # ArcGIS 裁剪、合并、PRJ 生成
    batch.py       # 批量流程编排
    cli.py         # 命令行入口
    estimates.py   # 估算 CSV 解析与分块规划
    files.py       # 栅格文件族复制、移动、删除
    settings.py    # 配置默认值与 ArcGIS Python 自动探测
    status.py      # 状态 CSV 写入
    tiles.py       # 瓦片坐标、下载、拼接
  tests/
    test_arcgis.py
    test_estimates.py
    test_tiles.py
    test_files.py
```

## 运行注意事项

- 这个工具默认面向 Windows，因为 ArcGIS Desktop / ArcPy 是工作流的一部分。
- 下载结果、瓦片缓存、ArcGIS 工作空间和日志都可能占用大量磁盘空间。
- 不要把下载生成的栅格结果或临时 GIS 输出提交到 Git。
- 如果任务中断，重新运行且不加 `--redo` 时，会优先复用已完成的裁剪块。
- `work_dir\tile_cache` 下的共享瓦片缓存默认会保留；如果你想回收空间或强制冷启动下载，可以手动删除它。
- 当前版本默认会保护旧的最终 GeoTIFF，只有新合并成功后才会替换。

## 常见问题

### 为什么包名里还是 `gansu`？

因为这个项目最初就是从甘肃县区数据流程里抽出来的。为了不破坏已有脚本和命令，模块名保留了下来，但逻辑本身是通用的。

### `reference_dir` 是不是每个省都要单独准备？

不是，而且现在它是可选的。不提供时，程序会借助 ArcPy 在工作目录里自动生成 `web_mercator_aux_sphere.prj`。

### 现在最少需要准备什么？

通常只需要一个面要素边界数据源和 `out_dir`。当你提供 `boundary_source` 时，程序可以自动生成估算 CSV、自动识别边界字段、自动补 `work_dir`，并在很多常见安装环境里自动找到 `arcgis_python`。

### `--redo` 会做什么？

它会忽略已有的裁剪块和最终输出，强制重新构建。

## 联系方式

如果你遇到问题，欢迎提交 GitHub Issue，也可以通过下面的邮箱联系我：

`2821452633@qq.com`
