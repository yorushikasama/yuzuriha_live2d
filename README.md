# 楪祈 Live2D 模型（yuzuriha）

用 **PSD2Live 自动绑定** 生成的 Live2D 半身模型，导出为 Cubism 标准格式，
浏览器端用 pixi-live2d-display 运行时渲染。

## 目录

```
├─ yuzuriha.psd              分层源图（29 MB，1536×1536）
├─ yuzuriha.psd2live         PSD2Live 工程（自包含，可重新导出）
├─ 模型说明.md                制作记录：踩过的坑、每轮修复的做法与结论
├─ Live2D-PSD分层与命名规范.md  分层/命名标准，以及"为运动而画"的要点
├─ 楪祈-素材补绘工单.md        眼睛/嘴/鼻的补画清单（含 AI 参考图 prompt）
├─ tools/                    PSD2Live MCP 客户端 + 渲染/导出脚本
└─ deploy/                   成品：网页 + 模型，可直接部署
   ├─ index.html             演示页（含缓存击穿，刷新即见最新导出）
   └─ yuzuriha/              模型文件（moc3 / 物理 / 动作 / 4096 贴图）
```

## 快速开始

```bash
# 本地预览（需要 HTTP 服务，直接开 file:// 会被 CORS 拦住）
cd deploy && python -m http.server 8899
# 然后打开 http://127.0.0.1:8899/index.html
```

## 建模链路

1. PSD 分层 → PSD2Live 导入，自动生成网格、变形器层级与参数绑定。
2. 用 `tools/psd2live_mcp.py` 通过 MCP 读写工程（令牌在注册表
   `HKCU\Software\JavaSoft\Prefs\io\github\psd2live\agent`）。
3. `tools/export.py` 导出并把运行时文件发布到 `deploy/yuzuriha/`。
4. `tools/render.py` 用 PSD2Live 自己的渲染器输出姿势对照表 —— 排查绑定问题时
   **以这个为准**，它是建模端的权威结果。

## 绑定要点（本轮修复）

- **全头单一驱动**：头部转向只由 `DeformHeadContainer` 承载，面部/眼/眉/耳/鼻/嘴/
  前后发的分支变形器不再各自重复叠加同一转动（否则各部件按不同倍率漂开）。
- **绕颈枢轴**：头绕 `DeformHeadContainer` 的局部 `[0.68, 0.30]`（≈颈根）旋转，
  下巴不再横向滑出脖子。
- **脖子剪切跟随**：`ArtMeshNeck` 顶点随头转向剪切 —— 发根钉在肩部、顶边跟下颌走，
  转头时下巴始终被脖子盖住（各姿势已逐帧数值校验）。

参数范围：`ParamAngleX ±20`、`ParamAngleY ±14`（运行时跟随与内置动作都在此范围内）。

## 已知待办

- **嘴巴**：源图只有一条闭口线，静息几乎不可见；张口素材（口腔/牙/舌）缺失，
  当前 `ParamMouthOpenY` 只能靠几何插值。计划在 Cubism Editor 里用 PSD 的嘴部素材补齐。
- **鼻子**：源图仅 6×7 px，同样留待 Cubism 里补画。
- **头部左右倾斜 `ParamAngleZ`**：自动绑定的旋转变形器支点不在下巴，靠 MCP 盲设几何
  会把头甩出画面，已压平。要做倾斜需在 Cubism GUI 里手动拖支点。
