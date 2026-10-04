# 两条源图路径

同一套绑定与运动效果，两套源图，各自独立产出。

| | [cyrene/](cyrene/) | [original/](original/) |
|---|---|---|
| 源图 | `source.psd` 19.3 MB / 23 层 | `source.psd` 27.7 MB / 22 层 |
| 脸 / 鼻 / 嘴 | Cyrene 的 | 原 PSD 自己的 |
| 头部墨迹（alpha≥64） | **42020** | 16020 |
| 眼睛 / 眉毛 | 楪祈的 | 楪祈的 |
| 身体 / 头发 / 四条飘带 | 楪祈的 | 楪祈的 |
| 模型产物 | `deploy/`（15 MB，完整） | 待构建 |
| 本地预览 | `cd variants/cyrene/deploy && python -m http.server 8899` | — |

**除脸鼻嘴外，两条路径的其余 19 层完全一致。**

原版的鼻子（6×7）和嘴巴（19×9）几乎只有几缕描边，墨迹量只有换脸版的 38%。
细节缺口记录在 [`楪祈-素材补绘工单.md`](../楪祈-素材补绘工单.md)。

## 怎么产生的

```bash
python tools/make_cyrene_psd.py     # 由 yuzuriha.psd 生成 cyrene 的 source.psd
```

脚本删除原 `face`/`nose`/`mouth`，加入四个 Cyrene 层，
并把层块插回原层序的同一位置（`ears-l` 之下、`eyelash-l` 之上，闭口在张口之上）。
确定性可重跑，两条路径因此永远同步。

## 导出到各自的 deploy

```bash
# 默认（cyrene）
python tools/export.py

# 显式指定
PSD2LIVE_VARIANT=cyrene   python tools/export.py
PSD2LIVE_VARIANT=original python tools/export.py
```

工程文件（`yuzuriha.psd2live`，226 MB）超 GitHub 100 MB 单文件限制未入库，
获取方式见 [REPRODUCE.md §3](../REPRODUCE.md)。
