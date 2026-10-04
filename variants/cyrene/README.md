# 路径二：Cyrene 换脸版（cyrene）

脸 / 鼻 / 嘴换成第三方模型 Cyrene 的，保留楪祈的眼睛、眉毛与全部身体服装。
**这是线上成品所用的路径。**

## 现状

| | |
|---|---|
| 源图 | `source.psd`（19.3 MB，23 层） |
| PSD2Live 工程 | `project.psd2live`（226 MB，见下方说明） |
| 模型产物 | `deploy/`（15 MB，网页可用） |

## 与另一条路径的差异

只有脸 / 鼻 / 嘴不同，其余 19 层完全一致。

| | 图层 | 墨迹像素（alpha≥64） | 尺寸 |
|---|---|---|---|
| **cyrene** | `cy_face` | 17124 | 141×164 |
| | `cy_nose` | 5751 | 79×107 |
| | `cy_mouth_open` | 9834 | 118×114 |
| | `cy_mouth_close` | 9311 | 118×108 |
| | 合计 | **42020** | |
| **original** | `face` | 15897 | 131×160 |
| | `nose` | 35 | 6×7 |
| | `mouth` | 88 | 19×9 |
| | 合计 | 16020 | |

头部墨迹量是原版的 **2.6 倍**。

## 源图是怎么来的

`source.psd` = `yuzuriha.psd` 删掉 `face`/`nose`/`mouth`，加入四个 Cyrene 层，
并把层块插回**原层序的同一位置**（`ears-l` 之下、`eyelash-l` 之上，闭口在张口之上）。

```bash
python tools/make_cyrene_psd.py     # 确定性可重跑
```

实测两张脸有 **48.5% 的像素不同**，差异区域 137×161 正好覆盖整张脸。

## 工程文件

`yuzuriha.psd2live`（仓库根，226 MB）就是本路径的 PSD2Live 工程——
由 `source.psd` 经自动绑定 + 六个脚本重播而成。

未纳入 Git（226 MB > GitHub 100 MB 单文件限制），获取方式见
[REPRODUCE.md §3](../../REPRODUCE.md)。

> 换脸路径不需要再跑 `make_cyrene_psd.py` 之外的额外步骤：
> 工程里的 `cy_*` 层就是 `source.psd` 里那四层，`replay_face_swap.py`
> 只在**从原始工程迁移**时用。

## 构建产物

```
deploy/
├─ index.html                  渲染器（含发珠渲染顺序修正 + 缓存击穿）
└─ yuzuriha/
   ├─ yuzuriha.model3.json     入口
   ├─ yuzuriha.moc3           模型（32 个画元 / 21 个参数）
   ├─ yuzuriha.4096/           3 页 4096 纹理
   ├─ yuzuriha.physics3.json   物理（含 PhysicsCloth 4 节点摆锤）
   ├─ yuzuriha.cdi3.json       画元/参数显示信息
   └─ *.motion3.json           idle / blink / nod / shake
```

**本地预览**：

```bash
cd variants/cyrene/deploy && python -m http.server 8899
# 打开 http://127.0.0.1:8899/index.html
```

## 换脸的坑

Cyrene 四层与 PSD originals 撞名，后者在 PSD2Live 里被自动改名为
`ArtMeshFace2` / `ArtMeshNose2` / `ArtMeshMouth`。

换脸收尾必须**打开新层、关闭旧层**，否则导出选项
`HiddenDrawableOmittedByExportOption` 会把新层整个踢出 moc，
结果 PSD2Live 和网页都显示旧脸——两边一致，但一致地错。

## 验收基准

| 项 | 期望 |
|---|---|
| 画元数 | 32（含 `cy_face_t` / `cy_nose_t` / `cy_mouth_open_t` / `cy_mouth_close_t`，不含 `face-t` / `nose` / `mouth`） |
| 参数数 | 21（含 `ParamClothSway` / `2` / `3`） |
| 物理组 | 4（前发 / 后发 / 果冻眼 / `PhysicsCloth`） |
| 后飘带峰值 | 49485 / 47421 px |
| 前飘带峰值 | 16910 / 15644 px |
| 上衣峰值 | 2 px（刚性） |

> **PSD2Live 1.3.0 的预览不模拟物理**（`ParamBodyAngleX=10` 持续 5 秒，
> 三个飘带参数和内置 `ParamHairFront` 全部恒为 0）。应用里看不到飘带摆动是正常的，
> `deploy/` 里的 physics3 才是真实效果。
