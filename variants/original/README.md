# 路径一：原版（original）

不换脸，保留楪祈 PSD 自己的脸 / 鼻 / 嘴。

## 现状

| | |
|---|---|
| 源图 | `yuzuriha.psd`（27.7 MB，22 层，未改动） |
| 模型产物 | `deploy/source/`（`source.*` 文件族，见下） |

## 产物目录名为什么是 `source`

PSD2Live 把导出文件族按**源文件名**命名。本路径的源图在
PSD2Live 里最初是以 `source.psd` 打开的，所以产物是 `source.*`。

若重开时用 `yuzuriha.psd`（现在的文件名），产物会变成 `yuzuriha.*`，
落在 `deploy/yuzuriha/`——与 cyrene 路径的约定一致。
`tools/export.py` 会自动跟随实际族名，不需要改代码。

## 与另一条路径的差异

只有脸 / 鼻 / 嘴不同，其余 19 层（身体、头发、服装、四条飘带、眼睛、眉毛）**完全一致**。

头部墨迹量（alpha ≥ 64）：

| | 图层 | 墨迹像素 | 实际尺寸 |
|---|---|---|---|
| **original** | `face` | 15897 | 131×160 |
| | `nose` | **35** | **6×7** |
| | `mouth` | **88** | **19×9** |
| | 合计 | 16020 | |
| **cyrene** | `cy_face` | 17124 | 141×164 |
| | `cy_nose` | 5751 | 79×107 |
| | `cy_mouth_open` | 9834 | 118×114 |
| | `cy_mouth_close` | 9311 | 118×108 |
| | 合计 | **42020** | |

**原版的鼻子和嘴巴几乎��空**——6×7 和 19×9 像素，也就是几缕描边残留。
这不是 bug，是原始素材本身的状态；细节缺口记录在 `楪祈-素材补绘工单.md`。

## 什么时候选这条路径

- 想要**纯净的原始素材**做二次创作
- 没有 Cyrene 素材可用
- 想对比"换脸前后"的差异

## 什么时候**不**选

- 想要和线上成品一致的观感 → 用 [cyrene](../cyrene/)
- 想要完整的五官细节 → 原版的鼻/嘴撑不起

## 如何构建

工程文件的绑定状态无法从 PSD 自动推导，需要在 PSD2Live 里手工走一遍：

```bash
# 1. PSD2Live 新建空白项目，导入 yuzuriha.psd，自动绑定
# 2. 打开 MCP agent，然后：
python -c "import sys; sys.path.insert(0,'../../tools'); from psd2live_mcp import Mcp; \
           m=Mcp(); m.initialize(); \
           m.call('settings', {'state': m.call('inspect',{'scope':'project'})['result']['structuredContent']['state'], \
                               'changes': {'alphaThreshold': 64}})"
#    alphaThreshold 必须 64：原 PSD 有 alpha 1-31 的噪声雾，会撑大包围盒
#
# 3. 重播绑定
python ../../tools/bind_head.py         # 头绕脖子旋转
python ../../tools/cloth_wave.py        # 后飘带三段链
python ../../tools/front_cloth.py       # 前飘带
python ../../tools/skirt_cloth.py       # 裙摆
python ../../tools/inapp_physics.py     # 应用内预览摆锤
#
# 4. 导出到本路径（会自动重跑物理补丁，并按实际族名建目录）
PSD2LIVE_VARIANT=original python ../../tools/export.py
#
# 5. 验收 —— 四条飘带峰值 > 10000 px、上衣 < 200 px
```

**不要跑 `replay_face_swap.py`**——那是换脸路径专用的。

## 已验证的验收基准

| 项 | 实测 |
|---|---|
| 画元数 | 33（`face-t` / `nose` / `mouth` + 唇描边两片，无 `cy_*`） |
| 参数数 | 21（含 `ParamClothSway` / `2` / `3`） |
| 物理组 | 4（前发 / 后发 / 果冻眼 / `PhysicsCloth` 4 节点摆锤） |
| 飘带峰值 | `[1, 1, 1]` 满量程 |
