# Gansu Batch Downloader

批量下载甘肃县区 Esri Wayback World Imagery 瓦片，拼接成整县 GeoTIFF，并用 ArcGIS 裁剪到县界。

## 功能

- 从估算表 `gansu_5m_county_estimate.csv` 读取县区瓦片范围
- 支持按县区 ID 选择任务，例如 `--areas 1,11,18` 或 `--areas 1-10`
- 大县自动拆成内部块下载、裁剪，最后合并成一个整县 GeoTIFF
- 瓦片并发下载并使用本地缓存
- 失败后可无 `--redo` 重跑，自动复用已完成的内部裁剪块
- 输出状态 CSV，便于查看完成/失败县区
- 依赖 ArcGIS Desktop/ArcPy 做裁剪和多块镶嵌

## 目录结构

```text
gansu-batch-downloader/
  src/gansu_downloader/
    arcgis.py      # ArcGIS/ArcPy 子进程裁剪、镶嵌、PRJ 生成
    batch.py       # 整县批量下载主流程
    cli.py         # 命令行入口
    estimates.py   # 估算 CSV 读取与县区分块
    status.py      # 状态 CSV
    tiles.py       # 坐标转换、瓦片下载、拼接
  configs/
    gansu.example.json
  scripts/
    run_gansu_example.ps1
```

## 环境

- Python 3.10+ 用于下载主程序
- ArcGIS Desktop 10.x 的 Python 2.7，用于 `arcpy`
- Python 依赖：`requests`、`Pillow`

安装依赖：

```powershell
cd E:\yanjiusheng\gansu-batch-downloader
E:\Python312\python.exe -m pip install -r requirements.txt
```

## 运行

查看计划，不下载：

```powershell
E:\Python312\python.exe -m gansu_downloader.cli `
  --estimate-csv E:\yanjiusheng\gansu_arcgis_ready\gansu_5m_county_estimate.csv `
  --out-dir E:\yanjiusheng\gansu_5m_whole_downloads `
  --work-dir E:\yanjiusheng\gansu_5m_work `
  --dry-run
```

下载全部县区：

```powershell
E:\Python312\python.exe -m gansu_downloader.cli `
  --estimate-csv E:\yanjiusheng\gansu_arcgis_ready\gansu_5m_county_estimate.csv `
  --out-dir E:\yanjiusheng\gansu_5m_whole_downloads `
  --work-dir E:\yanjiusheng\gansu_5m_work `
  --workers 16 `
  --max-tiles-per-chunk 2000 `
  --order largest-first
```

只补跑指定县区：

```powershell
E:\Python312\python.exe -m gansu_downloader.cli --areas 71,1,11,18,45,51,75 --workers 16
```

## 输出

默认整县成果：

```text
E:\yanjiusheng\gansu_5m_whole_downloads/
  gansu_001_5m_clipped.tif
  gansu_002_5m_clipped.tif
  gansu_download_status.csv
```

内部临时目录：

```text
E:\yanjiusheng\gansu_5m_work/
  raw/
  gansu_001/
  gansu_001_part_0001_clipped.tif
```

## 注意

下载成果、瓦片缓存、ArcGIS 工作库和日志体积都很大，不应提交到 Git。`.gitignore` 已排除这些文件。
