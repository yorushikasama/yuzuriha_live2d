# tools/ — PSD2Live MCP 辅助脚本

模型是用 **PSD2Live** 自动绑定生成的。它自带 MCP 接口
(`http://127.0.0.1:23871/mcp`),下面这些脚本通过该接口读写工程。

运行前需 PSD2Live 处于**打开工程**的状态。

## psd2live_mcp.py — MCP 客户端

```bash
# 列出全部 21 个工具
python psd2live_mcp.py tools

# 调用工具(参数给 JSON;Windows 路径用 @file.json 传入更稳)
python psd2live_mcp.py call inspect '{"scope":"objects","limit":64}'
python psd2live_mcp.py call export @args.json
```

令牌从注册表 `HKCU\Software\JavaSoft\Prefs\io\github\psd2live\agent`
读取。Java Preferences 会转义 `/`(`//` 表示 `/`,其他字符前缀 `/` 并大写),
**必须反转义**,否则每次请求 401 —— 脚本内已处理。

每次修改类调用会返回新的 `state`,**下一次调用必须带上**,否则报
`missing state`。

## render.py — 用 PSD2Live 自己渲染姿势对照表

```bash
python render.py '{"mode":"model","target_long_edge":900}' out.png
python render.py @req.json poses.png
```

排查绑定问题时**以这个为准** —— 它是建模端自己的渲染结果。
`mode` 可选 `model / poses / layer / coverage / context`。

注意:`mode=poses` 才认 `poses` 字段,`mode=model` 认 `parameters` 字段;
给错模式会静默渲染成中性姿势。`canvasRect` 返回的是字典
(`left/top/right/bottom`)而不是数组。

## export.py — 导出并发布到 deploy

```bash
python export.py
```

调用 `export` 导出到 `../out/`,再把有变化的文件复制到
`../variants/<路径>/deploy/yuzuriha/`。

## headpos.py — 量头部在画布中的位置

```bash
python headpos.py
```

用来诊断「头部在极端角度脱离身体」这一类问题。会打印中性姿势和
各角度下头部的画布坐标。

## 已知的绑定缺陷与处理

自动绑定的头部容器(`DeformHeadContainer`)是**纯平移**而非绕脖子旋转,
而 `ArtMeshNeck` 挂在身体变形器下**全程不动**。实测位移(1536 画布):

| 参数 | 位移 |
|---|---|
| AngleX=+45 | (+277, −37) |
| AngleX=−45 | (−162, +198) |
| AngleY=+30 | (−270, −536) |
| AngleY=−30 | (+227, +434) |

头部高度只有约 500 画布像素,所以 650px 的位移会把头整个拽离肩膀。

**处理方式**:收窄参数范围到 `ParamAngleX ±20`、`ParamAngleY ±14`
(内置动作只用到 ±20 / ±18,不受影响),这样运行时
`updateFocus()` 的 `30×光标位置` 也推不到失效区。

尝试过但**无效**的修法,记录以免重复:

- `deform` 平移 `DeformHeadContainer` / `DeformFaceNinePose` 的极端关键形态
  —— 调用成功返回 `changed`,导出的 moc3 哈希也确实变了,但渲染结果
  零变化;改用 `headStrength` 也只在部分角度有改善,组合极端角度仍会脱离。
