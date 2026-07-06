<a id="readme-top"></a>

# Batch Imagery Downloader

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![ArcGIS](https://img.shields.io/badge/ArcGIS-Desktop%2010.x-2C7AC3)](https://www.esri.com/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D4?logo=windows&logoColor=white)](https://www.microsoft.com/windows/)
[![GitHub Issues](https://img.shields.io/github/issues/Changsheng0727/batch-downloader)](https://github.com/Changsheng0727/batch-downloader/issues)
[![GitHub Stars](https://img.shields.io/github/stars/Changsheng0727/batch-downloader?style=social)](https://github.com/Changsheng0727/batch-downloader/stargazers)

[English](README.md) | [简体中文](README.zh-CN.md)

这是一个面向批量遥感任务的影像下载器：从 Esri Wayback World Imagery 下载瓦片，拼接成 GeoTIFF，再使用 ArcGIS/ArcPy 裁剪出最终结果。

这个项目最早来自甘肃县区影像下载流程，后来逐步整理成可复用的批处理工具。当前版本已经可以从“一个边界面数据源 + 一个输出目录”直接起步，自动生成估算 CSV、自动识别常见字段，并在重跑时复用共享瓦片缓存。

**相关链接**

- 项目地址：`https://github.com/Changsheng0727/batch-downloader`
- 问题反馈：`https://github.com/Changsheng0727/batch-downloader/issues`

## 目录

1. [项目简介](#项目简介)
2. [技术栈](#技术栈)
3. [快速开始](#快速开始)
4. [配置说明](#配置说明)
5. [使用方法](#使用方法)
6. [输出结构](#输出结构)
7. [项目结构](#项目结构)
8. [运行说明](#运行说明)
9. [后续规划](#后续规划)
10. [参与贡献](#参与贡献)
11. [许可证](#许可证)
12. [联系方式](#联系方式)
13. [致谢](#致谢)

## 项目简介

这个仓库面向的是长时间运行、数据量较大、需要稳定重跑的影像下载任务，而不是一次性的脚本。

当前版本的主要能力：

- 自动把大区域拆成更稳妥的内部块
- 不加 `--redo` 时自动复用已完成的裁剪块
- 下载线程复用 HTTP 会话，提高大批量抓取效率
- 下载到的瓦片保留在 `work_dir\tile_cache` 共享缓存中，重跑任务和相邻区域可直接复用
- 最终 GeoTIFF 只有在成功合并后才替换旧结果
- ArcGIS 中间裁剪阶段关闭不必要的金字塔和统计信息
- 可以直接从一个边界面要素类或 Shapefile 自动生成 `region_estimate.generated.csv`
- 能自动识别 `PAC`、`XZQDM`、`NAME`、`ascii` 等常见字段
- 能自动探测常见 Windows 安装位置下的 ArcGIS Python

处理流程：

```text
边界数据源或估算 CSV
  -> 需要时自动生成估算 CSV
  -> 选择区域 ID
  -> 大区域拆分为内部块
  -> 并发下载瓦片并使用缓存
  -> 每个块先拼接为原始 TIFF
  -> 使用 ArcGIS 对每个块裁剪
  -> 合并多个块为最终 GeoTIFF
  -> 写出状态 CSV
```

<p align="right">(<a href="#readme-top">回到顶部</a>)</p>

## 技术栈

- Python 3.10+
- ArcGIS Desktop 10.x / ArcPy
- Pillow
- Requests
- Windows

<p align="right">(<a href="#readme-top">回到顶部</a>)</p>

## 快速开始

### 前置条件

- Windows 机器
- 本地可用的 ArcGIS Desktop / ArcPy 运行环境
- Python 3.10 或更高版本

如果 ArcGIS Python 安装在常见位置，程序通常可以自动识别。

### 安装

1. 克隆仓库：

```powershell
git clone https://github.com/Changsheng0727/batch-downloader.git
cd batch-downloader
```

2. 以可编辑模式安装：

```powershell
python -m pip install -e .
```

3. 创建本地配置：

```powershell
copy configs\gansu.example.json configs\gansu.local.json
notepad configs\gansu.local.json
```

### 最少需要准备什么

大多数情况下，只需要：

- `boundary_source`
- `out_dir`

当你提供 `boundary_source` 后，程序通常还能自动推断：

- `id_field`
- `name_field`
- `ascii_field`
- `work_dir`
- `arcgis_python`

<p align="right">(<a href="#readme-top">回到顶部</a>)</p>

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

| 字段 | 是否必填 | 说明 |
| --- | --- | --- |
| `boundary_source` | 是，除非已经提供 `estimate_csv` | 用于自动生成估算 CSV 的面要素类 / Shapefile |
| `estimate_csv` | 是，除非已经提供 `boundary_source` | 已准备好的估算 CSV，包含区域范围、裁剪来源和输出命名信息 |
| `id_field` | 否 | 数值型唯一 ID 字段；省略时自动识别 |
| `name_field` | 否 | 显示名称字段；省略时自动识别 |
| `ascii_field` | 否 | 输出文件名前缀字段；省略时自动识别，不可用时回退为 `region_001` 这种名字 |
| `out_dir` | 是 | 最终裁剪 GeoTIFF 输出目录 |
| `work_dir` | 否 | 原始拼接结果、中间裁剪块、共享瓦片缓存和自动生成估算 CSV 的目录；默认是 `out_dir\_work` |
| `reference_dir` | 否 | 可选，若提供则应包含 `web_mercator_aux_sphere.prj`；否则由 ArcPy 自动写入工作目录 |
| `arcgis_python` | 否 | ArcGIS Desktop / ArcPy 的 Python 可执行文件；省略时自动探测 |
| `resolution` | 否 | 目标分辨率，默认 `5.0` 米/像素 |
| `wayback_id` | 否 | Esri Wayback 影像版本，默认 `58924` |
| `workers` | 否 | 下载并发数，默认 `12` |
| `max_tiles_per_chunk` | 否 | 每个内部块允许的最大瓦片数 |
| `order` | 否 | 处理顺序，可选 `id` 或 `largest-first` |
| `refresh_estimates` | 否 | 运行前强制重建自动生成的估算 CSV |
| `redo` | 否 | 即使已有结果也强制重建 |
| `keep_parts` | 否 | 保留中间裁剪块 |
| `dry_run` | 否 | 只输出计划，不实际下载 |

如果使用 `boundary_source`，自动生成的估算 CSV 会写到 `work_dir\region_estimate.generated.csv`，后续重跑默认复用，除非加上 `--refresh-estimates`。

<p align="right">(<a href="#readme-top">回到顶部</a>)</p>

## 使用方法

运行配置中的全部区域：

```powershell
python -m gansu_downloader.cli --config configs\gansu.local.json
```

不手工准备估算 CSV，直接运行：

```powershell
python -m gansu_downloader.cli --boundary-source D:\data\counties.shp --out-dir D:\imagery\out
```

先做干跑预览：

```powershell
python -m gansu_downloader.cli --config configs\gansu.local.json --dry-run
```

只运行指定 ID：

```powershell
python -m gansu_downloader.cli --config configs\gansu.local.json --areas 1,11,18
```

运行一个 ID 范围：

```powershell
python -m gansu_downloader.cli --config configs\gansu.local.json --areas 1-10
```

强制重建：

```powershell
python -m gansu_downloader.cli --config configs\gansu.local.json --areas 48 --redo
```

运行前刷新自动生成的估算 CSV：

```powershell
python -m gansu_downloader.cli --config configs\gansu.local.json --refresh-estimates
```

PowerShell 辅助脚本：

```powershell
scripts\run_gansu_example.ps1
```

<p align="right">(<a href="#readme-top">回到顶部</a>)</p>

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
  region_estimate.generated.csv
```

实际文件名前缀取决于估算 CSV 中的 `ascii` 字段；如果该字段缺失或不可用，程序会自动回退成 `region_001`、`region_002` 这类名字。

<p align="right">(<a href="#readme-top">回到顶部</a>)</p>

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
    test_files.py
    test_tiles.py
```

<p align="right">(<a href="#readme-top">回到顶部</a>)</p>

## 运行说明

- 这个工具默认面向 Windows，因为 ArcGIS Desktop / ArcPy 是工作流的一部分。
- 下载结果、缓存、ArcGIS 工作空间和日志都可能占用较大磁盘空间。
- 不要把下载生成的栅格结果或临时 GIS 输出提交到 Git。
- `work_dir\tile_cache` 下的共享瓦片缓存默认会保留；如果想回收空间或强制冷启动下载，可以手动删除。
- 包名仍然保留 `gansu`，主要是为了兼容更早的生产脚本。

<p align="right">(<a href="#readme-top">回到顶部</a>)</p>

## 后续规划

- [x] 基于边界数据源自动生成估算 CSV
- [x] 自动识别常见边界字段
- [x] 自动探测 ArcGIS Python
- [x] 持久化共享瓦片缓存
- [x] 使用真实 ArcGIS 做 dry-run 验证
- [x] 使用真实极小样例完成一次端到端下载与裁剪验证
- [ ] 针对超大区域降低内存占用的拼接策略
- [ ] 降低多分块场景下 ArcGIS 子进程开销
- [ ] 增加共享缓存的清理策略

更多改动建议和问题可以直接提到 [Issues](https://github.com/Changsheng0727/batch-downloader/issues)。

<p align="right">(<a href="#readme-top">回到顶部</a>)</p>

## 参与贡献

欢迎提交改进。

1. Fork 本仓库
2. 创建功能分支：`git checkout -b feature/your-change`
3. 提交修改：`git commit -m "Describe your change"`
4. 推送分支：`git push origin feature/your-change`
5. 发起 Pull Request

如果改动比较大，建议先开一个 issue 对齐思路。

<p align="right">(<a href="#readme-top">回到顶部</a>)</p>

## 许可证

这个仓库目前还没有单独提供 `LICENSE` 文件。

如果后续准备更正式地开源或分发，建议把许可证补上。

<p align="right">(<a href="#readme-top">回到顶部</a>)</p>

## 联系方式

- 邮箱：`2821452633@qq.com`
- 项目地址：`https://github.com/Changsheng0727/batch-downloader`

<p align="right">(<a href="#readme-top">回到顶部</a>)</p>

## 致谢

- [Best-README-Template](https://github.com/othneildrew/Best-README-Template)
- [Esri Wayback World Imagery](https://livingatlas.arcgis.com/wayback/)
- 更早期甘肃县区影像生产流程中的 ArcGIS / ArcPy 实战经验

<p align="right">(<a href="#readme-top">回到顶部</a>)</p>
