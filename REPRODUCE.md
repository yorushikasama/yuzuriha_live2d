# 复现指南：从 PSD 到成品模型

本文档让**没有参与过制作的人**能够从零复现楪祈 Live2D 模型的骨骼绑定与运动效果。

阅读顺序建议：先看 [§1 前置条件](#1-前置条件)，再按 [§6 完整流程](#6-完整流程) 逐步执行。
遇到问题查 [§7 已知坑](#7-已知坑)——那里的每一条都是实际踩过的。

---

## 1. 前置条件

| 项 | 版本 | 说明 |
|---|---|---|
| PSD2Live | 1.3.0 | 必需。自动绑定、网格生成、图集打包、物理配置全靠它 |
| PSD2Live MCP agent | 1.3.0 | 必需。提供 21 个 MCP 工具（`deform` / `canvas` / `physics` / `export` …） |
| Python | 3.10+ | 跑 `tools/` 下的脚本，只用标准库 |
| Cubism Core for Web | 4.x | 网页运行时，从 `cubism.live2d.com` CDN 加载 |

**MCP agent 的开启方式**：PSD2Live 内「设置 / Agent」面板启用，监听 `127.0.0.1:23871`。
Bearer token 存放在 Windows 注册表 `HKCU\Software\JavaSoft\Prefs\io\github\psd2live\agent`
的 `agent_mcp_bearer_token`（注意 Java 会把 `/` 转义成 `//`，`tools/psd2live_mcp.py` 已处理）。

**验证 MCP 连通**：

```bash
python tools/psd2live_mcp.py tools        # 应列出 21 个工具
```

---

## 2. 仓库内容

```
yuzuriha_live2d/
├─ yuzuriha.psd                 29 MB  分层源图 · 原版（1536×1536，22 层，未改动）
├─ yuzuriha_cyrene.psd          20 MB  分层源图 · 换脸版（23 层，脸鼻嘴换成 Cyrene）
├─ yuzuriha.psd2live           226 MB  PSD2Live 工程 = 绑定的真相（见 §3 说明）
├─ REPRODUCE.md                        本文
├─ 模型说明.md                         完整制作日志：13 章，每一步的判断依据与实测数据
├─ Live2D-PSD分层与命名规范.md          分层命名标准
├─ 楪祈-素材补绘工单.md                 已知素材缺口清单
│
├─ deploy/                            可直接部署的网页成品
│  ├─ index.html                      渲染器（含发珠渲染顺序修正）
│  └─ yuzuriha/                       模型文件族（moc3 + 3 页 4096 纹理 + 物理 + 动作）
│
├─ tools/                             全部自动化脚本（见 §5）
├─ docs/                              19 张验收图，每张对应一项修复
└─ assets/                            裁剪后的 35 张图层 PNG + manifest（见 §4.2）
   ├─ README.md                       用法与层序说明
   └─ trimmed/                        PNG + manifest.json
```

`out/`（导出中转）、`_local/`（Cyrene 参考模型、备份）已 gitignore，不参与复现。

---

## 3. 工程文件为什么不在 Git 里

`yuzuriha.psd2live` 有 **226 MB**，超过 GitHub 单文件 100 MB 限制（`*.psd2live` 在 .gitignore 里）。
它包含 280 个历史节点、自带的源 PSD 副本、以及全部 blob 存储。

**要复现绑定，你必须拿到这个文件**。三种获取方式：

1. 直接向模型作者索取（最省事）
2. 从 PSD 重新走一遍 [§6](#6-完整流程)，全部步骤已脚本化
3. 用 Git LFS 重新纳入版本库（`git lfs track "*.psd2live"`）

好消息是 §5 的脚本让路线 2 完全可行：绑定、飘带、脸、物理都有一键重播。

---

## 3.1 素材来源

本模型的美术由三方组成：

| 来源 | 内容 | 是否可再生 |
|---|---|---|
| `yuzuriha.psd` | 身体、头发、服装、四条飘带 | 仓库内（29 MB） |
| `assets/trimmed/` | 裁剪后的全部图层 | 仓库内（1.4 MB），或 `export_trimmed.py` 重导 |
| Cyrene 模型 | 脸、鼻子、嘴巴 | **外部**，见下 |

**脸/鼻/嘴来自一个第三方模型「Cyrene」**（本地留存于 `_local/Cyrene20251105/`，
未入库——它是别人的模型，且 36 MB）。复现者需要自备，
或改用原 PSD 的脸鼻嘴（效果较差，`楪祈-素材补绘工单.md` 列了具体缺口）。

飘带物理的**节点参数**（Delay / Mobility / Acceleration）参照了 Cyrene 的裙摆链调校，
这些数值已经写死在 `tools/patch_cloth_physics.py` 里，所以**复现飘带效果不需要 Cyrene**。

---

## 4. 关键设计决策

理解这几条，才知道脚本为什么这么写。

### 4.1 图集为什么是三页 4096

原 PSD 的图层**按整张 1536×1536 画布存储**，95% 是透明空地。
实测 back hair 的 alpha 分布：

| alpha 阈值 | 墨迹像素 | 包围盒 |
|---|---|---|
| ≥1 | 52107 | 1536×1536 (100%) |
| ≥16 | 49325 | 962×1536 (63%) |
| **≥32** | **48784** | **385×395 (6.4%)** |
| ≥64 | 48101 | 384×393 (6.4%) |

**alpha 1–31 是 PSD 隐藏的噪声雾**。`settings.alphaThreshold` 必须设为 **64**，
否则噪声撑大包围盒，网格和图集都会错位。

这也是高清化（`textureUpscale`）报 `Upscaled atlas exceeds 512 MiB` 的根因——
不是图集参数问题，而是存储方式问题。**1.3.0 无法在应用内修复**（见 §7.6）。

### 4.2 assets/trimmed/ 是什么

35 张按墨迹边界裁剪过的图层 PNG，1:1 原始像素，附 `manifest.json` 记录每层的画布坐标。
`tools/export_trimmed.py` 从运行中的工程导出它们。

用途：给不想重走美术流程的人一条捷径——用 `asset create` 直接建紧凑工程
（素材从 21.3 Mpx 降到 3.06 Mpx，图集 2 页 2048，×2 高清化只占 128 MiB）。

### 4.3 命名冲突：换脸的陷阱

Cyrene 的四层和 PSD originals 撞名：

| 期望 | 实际 | 说明 |
|---|---|---|
| `cy_face_t` → `ArtMeshFace` | ✓ | 抢到了原名 |
| `face-t`（旧） | → `ArtMeshFace2` | 被自动改名 |
| `cy_nose_t` → `ArtMeshNose` | ✓ | 抢到了原名 |
| `nose`（旧） | → `ArtMeshNose2` | 被自动改名 |

**换脸收尾时必须打开新层、关闭旧层**，否则导出选项 `HiddenDrawableOmittedByExportOption`
会把新层整个踢出 moc，结果 PSD2Live 和网页都显示旧脸。

---

## 5. 脚本清单

| 脚本 | 作用 | 幂等 |
|---|---|---|
| `psd2live_mcp.py` | MCP 客户端基类，所有脚本的基础 | — |
| `export.py` | 导出 + 发布到 `deploy/` + 自动重跑物理补丁 | ✅ |
| `replay_face_swap.py` | **一键重播换脸 + 眉毛层序**（应用重启后用） | ✅ |
| `bind_head.py` | 修复头/脖子绑定（头作为整体绕脖子旋转） | ❌ 一次性 |
| `cloth_wave.py` | 后飘带（`ArtMeshHandwearL/R`）三段嵌套 warp 链 | ✅ |
| `front_cloth.py` | 外侧两根前飘带（`ArtMeshTopwear` / `Topwear2`） | ✅ |
| `skirt_cloth.py` | 裙摆双飘尾（`ArtMeshTopwear3`） | ✅ |
| `inapp_physics.py` | 在应用内建三条预览摆锤（应用/导出一致） | ✅ |
| `patch_cloth_physics.py` | 导出后把飘带物理重写为单条 4 节点摆锤 | ✅ |
| `export_trimmed.py` | 导出裁剪后的图层 PNG + 坐标 | ✅ |
| `make_cyrene_psd.py` | 生成换脸版 PSD（`yuzuriha_cyrene.psd`） | ✅ |
| `build_motions.py` | 生成六段克制的 motion3 动作 | ✅ |
| `p2l_view.py` | 通过 MCP 触发应用内 view 渲染（调试用） | — |
| `alpha_noise_check.py` | 诊断 alpha 噪声对包围盒的影响 | — |
| `headpos.py` / `render.py` | 测量头部位置漂移 | — |

所有脚本支持环境变量覆盖路径（换机器不用改代码）：

```bash
export PSD2LIVE_ROOT=/path/to/yuzuriha_live2d
python tools/export.py
```

---

## 6. 完整流程

### 6.0 选哪份 PSD

仓库里有两份源图，**选哪份取决于你要复现什么**：

| | `yuzuriha.psd` | `yuzuriha_cyrene.psd` |
|---|---|---|
| 层数 | 22 | 23 |
| 脸 / 鼻 / 嘴 | 原 PSD 自己的 | **Cyrene 的** |
| 眼睛 / 眉毛 | 楪祈的 | 楪祈的（未动） |
| 上衣 / 头发 / 四条飘带 | 楪祈的 | 楪祈的（未动） |

原版的 `nose` 和 `mouth` 几乎是空的（alpha ≥ 64 时只有 35 / 88 个墨像素，
6×7 和 19×9 的几缕描边），所以换脸版的脸部细节明显更完整。

**两条路径都是完整的**：

- 想要和本仓库成品一致的观感 → 用 `yuzuriha_cyrene.psd`
- 想要纯净的原始素材、或没有 Cyrene 素材 → 用 `yuzuriha.psd`，
  脸鼻嘴会弱一些（缺口清单见 `楪祈-素材补绘工单.md`）

换脸版由脚本生成，可随时重建：

```bash
python tools/make_cyrene_psd.py
```

它做四件事：删除原 `face`/`nose`/`mouth`，加入 `cy_face`/`cy_nose`/
`cy_mouth_open`/`cy_mouth_close`，把它们插回原层序的同一位置
（`ears-l` 之下、`eyelash-l` 之上，闭口在张口之上），并校验墨量与层序。

> **psd-tools 1.19 的三个坑**（每个都花了一轮才摸清，已写进脚本注释）：
> 1. `layer.numpy()` 读的是原始通道数据，新建层读回来是空的；
>    要用 `layer.composite()` 才是真实像素。
> 2. `layer.visible = False` 在保存时**会丢弃像素**（face 从 15897 墨像素变 0），
>    所以要"隐藏"只能用 `remove()`。
> 3. `PixelLayer.frompil()` 把层加到**最底部**，要正确定位得用
>    `psd.insert(index, layer)`。

### 6.1 最短路径（拿到工程文件）

```bash
# 1. 用 PSD2Live 打开 yuzuriha.psd2live
# 2. 确认 MCP agent 已启动
python tools/psd2live_mcp.py tools

# 3. 重播全部绑定（应用重启后必做）
python tools/replay_face_swap.py     # 换脸 + 眉毛层序
python tools/cloth_wave.py           # 后飘带链
python tools/front_cloth.py          # 前飘带
python tools/skirt_cloth.py          # 裙摆
python tools/inapp_physics.py        # 应用内摆锤

# 4. 导出并发布（自动重跑物理补丁）
python tools/export.py

# 5. 在 PSD2Live 里 Ctrl+S 保存工程
```

### 6.2 完整路径（从 PSD 重建）

**步骤 1 — 导入并自动绑定**

PSD2Live 打开 `yuzuriha_cyrene.psd`（或 `yuzuriha.psd`，见 §6.0）。自动绑定会生成 25 个变形器：

```
DeformBodyXY (根)
└─ DeformBodyZBreath          身体 Z / 呼吸
   ├─ DeformPair_Handwear     手臂飘带对称组
   ├─ DeformPair_Legwear      腿饰对称组
   ├─ DeformPair_Footwear     鞋饰对称组
   ├─ neck, legwear-*, footwear-*
   └─ DeformHeadContainer
      └─ DeformHeadRotation → DeformFaceNinePose
         ├─ DeformFaceContour    脸（face-t / cy_face_t）
         ├─ DeformEyes → EyeShapeL/R → IrisPreserveL/R → EyeGazeL/R
         ├─ DeformBrows → BrowShapeL/R
         ├─ DeformEars → EarOcclusionL/R
         ├─ DeformNoseShapeBoth   鼻（nose / cy_nose_t）
         └─ DeformMouthShapeBoth  嘴（mouth / cy_mouth_*）
      ├─ DeformHairFrontFollow → DeformHairFrontPhysics
      └─ DeformHairBackFollow  → DeformHairBackPhysics
```

**步骤 2 — 关键设置**（`settings` 工具 / UI）

| 参数 | 值 | 为什么 |
|---|---|---|
| `alphaThreshold` | **64** | 滤掉 PSD 的 alpha 1–31 噪声雾（§4.1） |
| `atlasSize` | 4096 | 三页装得下；降到 2048 仍超限（存储尺寸决定，不是墨量） |
| `texturePadding` | 2 | |
| `headStrength` / `bodyStrength` | 1.0 | |
| `meshSpacing` | 40 | |
| `runtimeTarget` | Cubism50 | |

**步骤 3 — 头颈绑定修复**

```bash
python tools/bind_head.py
```

自动绑定会把转头重复施加在多个分支上（实测 `ParamAngleX=20` 时 face 漂移 +70,-39 px，
front hair +76,-41 px），且用裸平移把头带离脖子。此脚本把头绑成绕脖子旋转的整体。

**步骤 4 — 换脸**

```bash
python tools/replay_face_swap.py
```

用 Cyrene 的脸/鼻/嘴替换旧 PSD  originals，保留 yuzuriha 的眼睛和眉毛。
脚本同时修复眉毛层序（PSD 里 eyebrow 压在完全不透明的 face 之下，
合成 face+眼睛 与 face+眼睛+eyebrow 的像素差为 0 可证）。

**步骤 5 — 飘带（核心）**

```bash
python tools/cloth_wave.py     # 后飘带
python tools/front_cloth.py    # 前飘带
python tools/skirt_cloth.py    # 裙摆
```

三条链共享 `ParamClothSway` / `2` / `3`，形成相位渐变的行波。

**步骤 6 — 应用内摆锤**

```bash
python tools/inapp_physics.py
```

让 PSD2Live 预览与网页导出一致。**注意：1.3.0 的预览不模拟物理**
（`ParamBodyAngleX=10` 持续 5 秒，输出恒为 0），所以预览里仍看不到飘带摆动，
但导出的 physics3 是正确的。

**步骤 7 — 导出**

```bash
python tools/export.py
```

会自动重跑 `patch_cloth_physics.py`。**漏掉这步 = 飘带全部僵死**（§7.5）。

**步骤 8 — 验收**

```bash
python tools/export.py
# 检查 deploy/yuzuriha/yuzuriha.physics3.json
```

---

## 7. 已知坑

每一条都是实际浪费过时间的。

### 7.1 工具的 state 链式传递

每个变更类调用返回新的 `state`，下一次调用必须带回去，否则报
`Workspace HEAD changed: expected history-xxx, actual history-yyy`。

**而且 state 放在哪里因工具而异**：

| 位置 | 工具 |
|---|---|
| 顶层 `state` | `deform` / `form` / `settings` / `layer` / `structure` / `rig` / `export` / `preview` |
| `request.state` | `paint` / `parameter` / `asset` / `path` / `physics` / `canvas` |
| 不接受 | `view` / `inspect` / `revision` |

### 7.2 id 前缀两套写法

`appearance` 和 `structure` 的 `id` 要**裸 mesh 名**（`ArtMeshFace`），
而 `inspect` 只认 `mesh:` 前缀形式（`mesh:ArtMeshFace`）。
写错前缀 → `Object not found`。

### 7.3 inspect 的分页与空查询

- `scope=objects` 分页 **24 条/页**，用 `offset` 游标翻页
- **空 query 只返回 mesh，不返回 warp**——查 warp 必须 `query:"warp"`
- 不翻页会导致"存在性检查"永远返回空，脚本误判需要重建

### 7.4 `view` 的 target_long_edge 是目标值不是上限

它把**画布区域**缩放到指定尺寸，会放大小图层。且 `canvasRect` 报告的是
**墨迹包围盒**，不是画布区域——两者不一致时容易误判。

最小值 128。`view mode=model` 接受 `parameters`，不接受 `poses`（那是 `poses` 模式）。

### 7.5 物理补丁漏跑 = 飘带僵死

PSD2Live 原始导出的 physics3 里，飘带摆锤 id 是 `PhysicsClothPreview1/2/3`
（应用内预览用的 2 节点摆锤）。发布到网页的必须是 `patch_cloth_physics.py`
生成的 `PhysicsCloth`（4 节点单链，三个输出取 node1/2/3，Scale 3.0/4.5/6.0）。

`export.py` 现在会自动重跑补丁。**若手工拷贝导出文件，务必手动补跑。**

### 7.6 高清化在 1.3.0 无法使用

`textureUpscale` 报 `Upscaled atlas exceeds 512 MiB of raw pixels`。
根因是 §4.1 的全画布存储，不是参数问题。**1.3.0 没有在应用内修复的接口**：

- `asset reprocess` 只能处理已注册的素材，够不到 PSD 原始图层
- `asset remove` 删不掉 PSD 来源层（三个注册表 id 对不上）
- 隐藏层仍占图集格子；装箱是增量的，格子永不回收
- 实证 `atlasSize=2048 + scale=2` 仍超限

绕行方案见 §4.2（`assets/trimmed/` + `asset create`）。

### 7.7 工具参数格式的坑

- `deform` 的 operation 需要**显式 `type`**（`translate`/`scale`/`rotate`/`arc`/`curve`/`landmarks`），
  只给 `delta` 会被拒（`choose one declared operation`）
- `form` 的 `set` 变体用 `channels: {"opacity": 1.0}` 对象映射，不是数组
- `asset create` 的 `x`/`y` **必须是整数**（浮点报 JSON parse error）
- `asset create` **要求空工作区**且单次上限 32 层
- `canvas` 的 `warp` 创建不要传 `bounds`，否则导出时报网格塌陷

### 7.8 物理必须在 update 之前求值

```javascript
if (phys && phys.evaluate) phys.evaluate(core, 1/60);
core.update();
app.render();
```

顺序错了读到的都是上一帧的值。另外 pixi-live2d-display 0.4.0 的 rAF
在后台标签页不推进，自动化测试必须手动步进。

---

## 8. 验证基准

复现后应该得到这些数字（`_work/verify_ribbons.py` 的方法：互不重叠取样框，
统计 alpha 差 >24 的像素数）：

| 参数 | 后飘带L | 后飘带R | 前飘带L | 前飘带R | 上衣 |
|---|---|---|---|---|---|
| Sway +1 | 43583 | 47421 | 15193 | 15644 | **0** |
| Sway -1 | 49485 | 42338 | 16910 | 14847 | **2** |
| Sway2 +1 | 37139 | 39212 | 8718 | 8601 | **0** |
| Sway3 +1 | 24410 | 24720 | 1627 | 1495 | **0** |

**判据**：四条飘带峰值 > 10000 px，上衣峰值 < 200 px（刚性），
位移随 S1→S2→S3 递减（三段链的深度加权）。

导出后 `yuzuriha.cdi3.json` 应有 **21 个参数**（含 3 个 `ParamClothSway*`）
和 **32 个画元**（含 `cy_face_t` / `cy_nose_t` / `cy_mouth_open_t` / `cy_mouth_close_t`）。
