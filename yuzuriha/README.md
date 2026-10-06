# 楪祈 Live2D 博客部署包

模型由 **PSD2Live** 自动绑定生成(免手工 Cubism 操作),导出为 Cubism 标准格式,
网页端用 **pixi-live2d-display** 渲染。

---

## 一、文件结构

```
├─ index.html                     网页运行时(可改配置)
├─ README.md                      本文件
├─ yuzuriha.model3.json           模型入口,运行时读这个
├─ yuzuriha.moc3                  模型本体
├─ yuzuriha.physics3.json         物理(头发/飘带摆动)
├─ yuzuriha.cdi3.json             参数显示名(调试用)
├─ yuzuriha.idle.motion3.json     待机循环 6s(含呼吸/眨眼/身体摇摆)
├─ yuzuriha.blink.motion3.json    眨眼 1.2s
├─ yuzuriha.nod.motion3.json      点头 2s
├─ yuzuriha.shake.motion3.json    摇头 2s
└─ yuzuriha.4096/                 贴图 ×3(4096 图集)
```

所有文件与本 README 同级。`cmo3` 工程与 `psd2live.json` 绑定清单不随包发布,
需要源文件时向仓库索取(见仓库根 README)。

## 二、改配置

打开 `index.html`,顶部 `CONFIG` 区:

```javascript
const CONFIG = {
  model: "./yuzuriha.model3.json",           // 模型路径
  x: 0.5, y: 1.0,        // 锚点(屏幕比例):0.5/1.0 = 底部居中
  fitHeight: 0.98,       // 角色高度占视口的比例
  idleMotion: "Idle",    // 待机动作组名
};
```

侧边栏挂件把 `y` 调成 `0.6`、`fitHeight` 调成 `0.5` 之类即可。

## 三、部署到博客

### 方式 A:静态托管(推荐)

把整个文件夹上传到博客静态目录或对象存储,保持 `index.html` 与
`yuzuriha.*` 同级即可。模型贴图共约 14 MB,建议开 gzip/br 与长缓存。

### 方式 B:iframe 挂件

```html
<iframe src="https://你的域名/inori/index.html"
        style="position:fixed; right:0; bottom:0; width:400px; height:600px;
               border:none; z-index:9999;"
        allow="fullscreen"></iframe>
```

想不挡正文点击,加 `pointer-events:none;`(但模型就不能互动了)。

### 方式 C:直接嵌进模板

把 `index.html` 里的 `<style>` 与 `<script>` 贴进博客模板,
`CONFIG.model` 改成模型文件的完整 URL。

## 四、注意事项

- **协议一致**:HTTPS 页面不能加载 HTTP 资源,模型文件要和页面同协议;
- **CORS**:模型放在别的域名时,对方要允许跨域(或干脆放同域);
- **Live2D Core 走 CDN**:`live2dcubismcore.min.js` 从官网 CDN 加载;
  完全离线部署要把它一并本地化;
- **点击反应**:PSD2Live 不导出 HitAreas,所以 `model.on("hit")` 不会触发。
  `index.html` 里改成按坐标命中头部区域,点角色的头会随机播 `Nod` / `Shake`;
- **鼠标跟随**:视线与头部会跟随光标,这是运行时自动行为,无需配置。
  头部角度范围已收窄到 ±20°/±14°(`ParamAngleX/Y`),因为自动绑定的头部
  在更大角度下会脱离身体 —— 细节见 `../模型说明.md` 第五节。

## 五、本地预览

在本目录起一个静态服务器(不能直接双击 html,浏览器会拦本地模型请求):

```bash
python -m http.server 8765
```

然后访问 http://127.0.0.1:8765/index.html

## 六、再修改模型

模型是 PSD2Live 工程 `../yuzuriha.psd2live` 导出的。需要调整绑定时,
用它打开该工程改完重新导出,替换本目录的模型文件即可。
`../tools/` 下有配套脚本:

```bash
# 列出 PSD2Live 暴露的 MCP 工具(需软件处于运行状态)
python ../tools/psd2live_mcp.py tools

# 调用某个工具
python ../tools/psd2live_mcp.py call inspect '{"scope":"objects"}'

# 让 PSD2Live 自己渲染一组姿势做对照(输出 png)
python ../tools/render.py '{"mode":"model","target_long_edge":900}' out.png
```
