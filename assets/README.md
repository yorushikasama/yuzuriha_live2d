# assets/trimmed — 裁剪后的图层素材

35 张 1:1 原始像素的图层 PNG，共 6.18 Mpx（1.4 MB）。

## 是什么

每个 PNG 是**从运行中的 PSD2Live 工程导出的单个图层的墨迹区域**，
裁剪时剔除了 alpha < 32 的 PSD 噪声雾（见 REPRODUCE.md §4.1）。
`manifest.json` 记录每层的画布坐标：

```json
{
  "name": "back hair",
  "source_layer_id": "lyid:3",
  "file": "38_back_hair.png",
  "x": 572, "y": 33, "w": 389, "h": 399,
  "rendered": [1536, 1536]
}
```

`rendered` 是裁剪前的画布区域尺寸，`x/y/w/h` 是裁剪后 PNG 在 1536×1536 画布上的落位。

## 为什么需要它

原 PSD 的图层按**整张 1536×1536 画布**存储，95% 是透明空地。
这导致图集需要 3 页 4096，PSD2Live 1.3.0 的高清化功能直接超限无法使用
（详见 REPRODUCE.md §7.6）。

用这些裁剪图走 `asset create` 可以建出紧凑工程：素材降到 3.06 Mpx，
图集 2 页 2048，**×2 高清化只占 128 MiB**（上限的 25%）。

## 怎么用

```python
import json, os, sys
sys.path.insert(0, "tools")
from psd2live_mcp import Mcp

mf = json.load(open("assets/trimmed/manifest.json", encoding="utf-8"))
m = Mcp(); m.initialize()

# asset create 要求空工作区，且单次上限 32 层
# 这里排除 3 个空壳层（headwear / mouth / nose，墨迹仅 19×24、19×9、6×7 像素）
DROP = {"headwear", "mouth", "nose"}
keep = [e for e in mf if e["name"] not in DROP]

m.call("asset", {"request": {
    "mode": "create", "width": 1536, "height": 1536,
    "layers": [{"path": os.path.abspath(os.path.join("assets/trimmed", e["file"])),
                "name": e["name"], "x": e["x"], "y": e["y"]} for e in keep],
}})
```

然后按 REPRODUCE.md §6.1 重放绑定脚本。

**注意**：`asset create` 会**原样保留**传入的图层顺序，cdi3 的 index 0 就是传入的第一项。
想复现正确的层序，请参照 `deploy/yuzuriha/yuzuriha.cdi3.json` 的 `Drawables` 顺序。

## 重新生成

```bash
python tools/export_trimmed.py
```

需要 PSD2Live 正在运行且工程已加载。
