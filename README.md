# 楪祈 Live2D 模型（yuzuriha）

用 **PSD2Live 自动绑定** 生成的 Live2D 半身模型，导出为 Cubism 标准格式，
浏览器端用 pixi-live2d-display 运行时渲染。

> **要复现这个模型的绑定与运动效果，请看 [REPRODUCE.md](REPRODUCE.md)。**
> 本文只做项目概览；逐步复现步骤、绑定层级图、验收基准、已知坑全在 REPRODUCE.md。

## 目录

```
├─ yuzuriha.psd                 29 MB   分层源图 · 原版（22 层，未改动）
├─ yuzuriha_cyrene.psd          20 MB   分层源图 · 换脸版（23 层，脸鼻嘴用 Cyrene 的）
├─ yuzuriha.psd2live           226 MB   PSD2Live 工程 = 绑定的真相
│                                      （超 GitHub 100MB 限制未入库，见 REPRODUCE.md §3）
├─ REPRODUCE.md                         复现指南：前置条件 / 完整流程 / 已知坑
├─ 模型说明.md                          制作日志：13 章，每步的判断依据与实测数据
├─ Live2D-PSD分层与命名规范.md           分层/命名标准，以及"为运动而画"的要点
├─ 楪祈-素材补绘工单.md                  眼睛/嘴/鼻的补画清单（含 AI 参考图 prompt）
│
├─ variants/                           两条源图路径，各自独立（见下）
│  ├─ cyrene/                          换脸版：yuzuriha.psd + deploy/（网页成品）
│  └─ original/                        原版：  yuzuriha.psd + deploy/（待构建）
│
├─ tools/                              全部自动化脚本（幂等，可重复执行）
├─ docs/                               19 张验收图，每张对应一项修复
└─ assets/trimmed/                     裁剪后的 35 张图层 PNG + 坐标 manifest
```

`out/` 与 `_local/` 是本地工作目录，已 gitignore，不参与复现。

## 两条源图路径

| | [variants/original/](variants/original/) | [variants/cyrene/](variants/cyrene/) |
|---|---|---|
| 脸 / 鼻 / 嘴 | 原 PSD 自己的 | **Cyrene 的** |
| 头部墨迹（alpha≥64） | 16020 | **42020** |
| 其余 19 层 | 楪祈的 | 楪祈的（未动） |
| 模型产物 | 待构建 | `deploy/`（完整） |

**除脸鼻嘴外两条路径完全一致。** 原版的鼻子（6×7）和嘴巴（19×9）几乎只有几缕描边。

## 快速开始

```bash
# 本地预览（需要 HTTP 服务，直接开 file:// 会被 CORS 拦住）
cd variants/cyrene/deploy && python -m http.server 8899
# 然后打开 http://127.0.0.1:8899/index.html
```

## 建模链路

1. PSD 分层 → PSD2Live 导入，自动生成网格、变形器层级与参数绑定。
2. 用 `tools/psd2live_mcp.py` 通过 MCP 读写工程（令牌在注册表
   `HKCU\Software\JavaSoft\Prefs\io\github\psd2live\agent`）。
3. 按 REPRODUCE.md §6 依次重播绑定脚本（换脸、飘带、裙摆、摆锤）。
4. `tools/export.py` 导出并把运行时文件发布到 `variants/<路径>/deploy/yuzuriha/`，
   **并自动重跑物理补丁**（漏跑会让飘带全部僵死，见 REPRODUCE.md §7.5）。
   用 `PSD2LIVE_VARIANT=original|cyrene` 选目标路径。
5. 浏览器内逐帧验收：飘带联动、头颈贴合、眉毛可见性。

## 绑定根因与修复（本轮的真正问题）

**症状**：转头时整个头（连前发、五官）横向滑出脖子，脖子原地不动，模型看着像"没有绑定"。

**根因不在绑定层级，而在 PSD 的隐藏 alpha 噪声。**
`face` 图层在整张 1536×1536 画布上散布着 **341,759 个 alpha 仅 1–3/255 的像素**
（≈0.4–1.2% 不透明度，肉眼完全不可见），`nose`/`mouth`/`neck`/前后发同样如此，
且这些图层都**没有图层蒙版**，混合模式也是 Normal。

PSD2Live 用 `DEFAULT_ALPHA_THRESHOLD = 1`（任何非零 alpha 都算不透明）来求图层
包围盒，于是把这些图层的范围算成了整张画布，`faceRig` 因此得出：

| 锚点 | 修复前 | 修复后 | 真实值 |
| --- | --- | --- | --- |
| `radiusX` | 1335.8 | **70.9** | 脸半宽 ≈ 65 |
| `radiusY` | 1455.3 | **100.2** | 脸半高 ≈ 80 |
| `centerY` | 378.7 | **173.8** | 脸中心 ≈ 160 |
| `initialAngleZ` | −28.78° | **0.0°** | 正视 ≈ 0 |

头部转向的位移量正比于 `radiusX/radiusY`，半径虚高 **约 19 倍**，所以 `ParamAngleX=30`
时脸被推出 106 px、而挂在身体上的脖子纹丝不动 —— 看起来就是"头没绑到脖子上"。

**修复**：`settings.alphaThreshold` 由默认 1 改为 **64**。
实测阈值 64 恰好滤掉所有杂点（1→3 与那个孤立的 (1535,1535) 像素），
同时完整保留真实笔触（`mouth` 88 px、`nose` 35 px 全部位于脸部）。

**效果**（浏览器内实测，`t64` 实测值）：

| 指标 | 修复前 | 修复后 |
| --- | --- | --- |
| `ParamAngleX=30` 时脸位移 | 106 px | **7 px** |
| 脸与脖子中心横坐标差 | 106 px | **0–7 px** |
| 下颌到底边距离（各姿势） | 漂移 | **稳定 −47 px** |
| 嘴/鼻是否落在脸上 | 否 | **全部姿势 是** |

同时 `face-b` 因不再是"全画布"而被正确识别为空图层并跳过。

## 绑定要点（层级部分）

- **全头单一驱动**：头部转向由 `DeformHeadContainer`（九宫格弯曲变形器）承载，
  父级依次为 `rotation:DeformHeadRotation` → `warp:DeformBodyZBreath` → `DeformBodyWarp`；
  面部/眼/眉/耳/鼻/嘴/前后发的分支变形器不再各自重复叠加同一转动。
- **枢轴在嘴线（≈下巴）**：`RigBuilder` 取 `headPivotY = faceRig.mouthLineY`。
  alphaThreshold 修正后枢轴回到真实下巴位置，于是 `ParamAngleZ ±30°` 变成了
  **真正绕下巴的点头式侧倾**（修复前半径虚高，这个旋转只会把头甩出画面）。
- **脖子挂在身体上、不放进头部旋转器**：`ArtMeshNeck` 归 `DeformBodyZBreath`
  （在头部旋转器之外）。这正是 Cubism 手册对脖子的建议 —— 头绕下巴转、
  不拽着脖子。实测 `ParamAngleZ ±30°` 时，脸/前发/后发整体刚性旋转 ±30°，
  而脖子**自身朝向完全不变**（Δ0.00°）；因枢轴就在下巴（旋转时下巴几乎不动）
  且脖子根部被领口遮住，全姿势扫描**没有任何一行出现透明断缝**。

参数范围：`ParamAngleX ±45`、`ParamAngleY ±30`、`ParamAngleZ ±30`（运行时 focus
controller 会用到全范围，内置 idle/nod/shake 动作幅度更小）。

## 运行时实测（本轮，浏览器内逐帧验证）

| 项目 | 方法 | 结果 |
| --- | --- | --- |
| 头是否长在脖子上 | 全范围定格，量脸/脖中心横坐标差 | 静息 0.8 px，Idle/Nod/Shake 全程 0.6–9.2 px |
| 转头是否真的"转" | 量鼻尖在脸包围盒内的相对位置 | 静止 49.7% → X−45 时 41.1% → X+45 时 58.2%（有立体视差，不是整片平移） |
| 侧倾是否绕下巴 | 量双眼连线夹角 | Z=+30 时眼线转 −29.2°、鼻 −30.0°、前发 −30.0°、后发 −30.0°（四者同步） |
| 脖子是否脱节 | 量脖子自身主轴朝向 + 全行扫描透明缝 | 脖子朝向 Δ0.00°（始终不动，符合手册）；接缝**零透明行** |
| 前发是否跟头 | `ParamHairFront=±1` 定格 | 位移 0.0 px（完全刚性，只随头部容器走） |
| 眨眼 | EyeOpen 1 / 0.5 / 0 | 眼白高度 18.8 → 10.7 → 7.8 px，眼睑正常闭合 |
| 眼球跟随 | EyeBallX/Y = ±1 | 瞳孔各移动 ±2.8 px |
| 鼠标跟随链路 | 派发真实 pointermove | focus 目标值随光标到 ±1，头/眼参数跟随（见下"调试注意"） |

## 飘带（四条独立联动）

后飘带、外侧两根前飘带、裙摆双飘尾各有一条**三段嵌套 warp 链**，
共享 `ParamClothSway` / `2` / `3`，形成沿飘带向下传播的相位渐变波。

| 部位 | 网格 | 脚本 | 弧根位置 |
|---|---|---|---|
| 后飘带 | `ArtMeshHandwearL/R` | `cloth_wave.py` | 0.18 / 0.42 / 0.62 |
| 外侧前飘带 | `ArtMeshTopwear` / `Topwear2` | `front_cloth.py` | 0.34 / 0.55 / 0.70 |
| 裙摆双飘尾 | `ArtMeshTopwear3` | `skirt_cloth.py` | 0.32 / 0.55 / 0.75 |

裙摆那层的弧根特意设在**开衩处**而非图顶，否则上衣会被一起拖动。

**实测**（互不重叠取样框，统计 alpha 差 >24 的像素数）：

| 参数 | 后飘带L | 后飘带R | 前飘带L | 前飘带R | 上衣 |
|---|---|---|---|---|---|
| Sway +1 | 43583 | 47421 | 15193 | 15644 | **0** |
| Sway2 +1 | 37139 | 39212 | 8718 | 8601 | **0** |
| Sway3 +1 | 24410 | 24720 | 1627 | 1495 | **0** |

位移随 S1→S2→S3 递减，正是三段链的深度加权；上衣峰值 0–2 px 保持刚性。

**物理**：PSD2Live 只能生成独立的 2 节点摆锤，且用参数串联摆锤时下游读数会衰减到 0。
`patch_cloth_physics.py` 在导出后把飘带物理重写为**单条 4 节点摆锤**，
三个输出按深度取 node1/2/3（Scale 3.0 / 4.5 / 6.0）。节点参数参照 Cyrene 的裙摆链调校：
Delay 拉满（延迟大而丝滑，非弹簧感），Mobility 沿链递增，Acceleration 递减。

> **PSD2Live 1.3.0 的预览不模拟物理**——`ParamBodyAngleX=10` 持续 5 秒，
> 三个飘带参数和内置的 `ParamHairFront` 全部恒为 0。所以应用里看不到飘带摆动是正常的，
> 导出的 physics3 才是真实效果。`inapp_physics.py` 建的三条预览摆锤只为让工程状态自洽。

## 换脸（Cyrene）

用 Cyrene 的脸/鼻/嘴替换旧 PSD originals，保留 yuzuriha 的眼睛和眉毛
（它们在脸层之上，是用户明确要保留的部分）。`replay_face_swap.py` 可一键重播。

**源图有两份**：`yuzuriha.psd`（原版，22 层）与 `yuzuriha_cyrene.psd`（换脸版，23 层）。
后者由 `python tools/make_cyrene_psd.py` 生成，删掉原 `face`/`nose`/`mouth`、
加入四个 Cyrene 层、并把它们插回原层序的同一位置。
实测两张脸有 48.5% 的像素不同，差异区域 137×161 正好覆盖整张脸。

**命名冲突是这里最大的坑**：Cyrene 四层与 PSD originals 撞名，
后者被自动改名为 `ArtMeshFace2` / `ArtMeshNose2` / `ArtMeshMouth`。
换脸收尾必须**打开新层、关闭旧层**，否则导出选项
`HiddenDrawableOmittedByExportOption` 会把新层整个踢出 moc，
结果 PSD2Live 和网页都显示旧脸（两边一致，但一致地错）。

## 已知待办

- **嘴巴素材**：当前嘴用的是 PSD 自己的墨线（约 16×7 px），位置正确（落在脸部范围内，
  PSD 坐标 ≈(767, 216)，与 PSD 源图墨线 x[757,777] y[211,219] 吻合），`ParamMouthOpenY`
  0→0.5→1 时高度 1.1→3.7→7.5 px 能正常开合；但静息只有 1 px 高，**张口素材
  （口腔/牙/舌）源图里没有**，只能靠几何插值。留待 Cubism Editor 用 PSD 素材补齐。
- **鼻子**：源图仅 6.6×7.4 px，位置正确、随头转动，同样留待 Cubism 里补画。
- **眉毛已修**（draw_order）：PSD 里 `eyebrow` 图层本就压在不透明的 `face`
  图层之下，PSD2Live 照搬层序导致眉毛被脸盖住。已用 MCP `structure` 把三个
  眉网格提到脸之上（仍在刘海之下），`ParamBrowLY/RY` 挑眉动画随之可见。
  详见 `模型说明.md` 第七章。

> 注：alphaThreshold 修正也顺带治好了嘴。修复前 `mouth` 图层因 (1535,1535) 那个
> 孤立 alpha=39 像素被撑成整画布包围盒，网格落到披风上；现在阈值滤掉了它，
> 嘴的网格自然回到 PSD 墨线的真实位置。

### 调试注意（本轮踩的坑）

无头自动化标签页里 **`requestAnimationFrame` 不触发**（实测 2.46 s 内 0 帧），
于是页面自身不动画、`ParamAngle*` 读出来全是 0 —— 这不代表绑定坏了。
另外 `IModel.update()` 每轮末尾会 `loadParameters()` 把参数复位，帧后读参数拿不到有效值。
**正确做法**：手动泵 `PIXI.Ticker.shared` + `app.ticker`，并以**顶点几何**（而非参数值）
作为判据。
