# 脸盘框架与素材生成器

## 渲染结构

每个宝可梦皮肤（`PokemonAvatar`）都是一个 320×240 的面板，从下往上依次是：

1. 面板底色：`backdrop`。只有在背景图做了镂空时才看得到。
2. **头后特效层**（`behind`）：比如小火龙的火焰。
3. 背景图 `bg`：RGB565 格式；做镂空的话用 RGB565A8，头部以外是透明的。
4. 左眼、右眼（`PokemonEye`）、嘴（`PokemonMouth`）：都是 RGB565A8 精灵图。
5. **头前特效层**：皮卡丘的电光、杰尼龟的墨镜。
6. 气泡：沿用原版的 `DefaultSpeechBubble`，现在只用来显示系统消息。

技能图标不属于皮肤，它画在屏幕的最上层。不管当前是哪张脸，包括原版脸，都会显示。

### 和原版动画对接

眼睛和嘴实现的是 StackChan 的 `Feature` 接口，所以原版的修饰器不用改就能驱动它们：

| 接口 | 皮肤里的效果 |
| --- | --- |
| `setEmotion` | 换成该情绪的眼睛或嘴巴精灵图 |
| `setWeight`（眼睛） | 低于 30 时显示闭眼图，眨眼就是靠这个 |
| `setWeight`（嘴） | 低于 12 显示当前情绪的嘴型，12 到 55 显示小张嘴，55 以上显示大张嘴，说话就是靠这个 |
| `setPosition` | 眼睛在 ±12 像素内移动，嘴在 ±10 像素内移动（呼吸、张望） |
| `setSize`（眼睛） | 缩放（待机时的小表情） |
| `setRotation`（嘴） | 旋转（晃动设备时的晕眩） |

### 内存

- 素材以 PNG 形式编进固件。切换角色时，用 LVGL 自带的 lodepng 解码，再转成 RGB565 或 RGB565A8，放进 PSRAM。
- 注意：LVGL 版的 `lodepng_decode32` 返回的是一个 `lv_draw_buf_t*`，不是普通的像素数组，要用 `lv_draw_buf_destroy` 释放。
- 切换时先解码新角色，再替换掉旧的脸。旧脸的 LVGL 对象删掉之后，它的图片才会释放。

## 素材生成器

`firmware/tools/pokemon_faces/gen_faces.py` 用 Pillow 程序化绘制所有素材：先按 4 倍尺寸画，再缩小，以得到平滑的边缘。

```bash
cd firmware/tools/pokemon_faces
uv venv .venv && uv pip install --python .venv/bin/python pillow numpy
.venv/bin/python gen_faces.py
```

它会输出：

- `out/*.png`：每张素材，以及 `contact_sheet.png`（所有角色乘以所有表情的总览）和 `icons.png`；
- `firmware/main/stackchan/avatar/skins/pokemon/pokemon_assets.c`：嵌入固件用的 C 数组，再加上 3 张表：素材表、特效层表、皮肤表。

改完素材后重新运行生成器，然后执行 `idf.py build`。新增或删除源文件之后，要先执行一次 `idf.py reconfigure`。

### 生成器结构

| 部分 | 作用 |
| --- | --- |
| `CHARS` | 每个角色的配色和标志：`nose`、`fangs`、`wide`、`shades`、`cutout`、`dots` 等 |
| `draw_eye(c, state, left)` | 眼睛：大眼睛或豆豆眼。生气、难过、疑惑、困、酷这几种用斜切的眼睑表现 |
| `draw_mouth(c, state)` | 嘴：各情绪的嘴型，加上说话时的小张嘴、大张嘴，以及鼻子（鼻子画在嘴的精灵图里，跟着嘴一起动） |
| `draw_background(name, c)` | 头型、渐变、轮廓线、高光、腮红和各角色的标志 |
| `fx_layers(name)` | 特效层：位置、各情绪的帧、是否放在头后面 |
| `ICONS` | 技能图标 |

### 加一个新角色

1. 在 `CHARS` 里加一项。如果需要特殊的标志，在 `draw_background` 里加对应的分支。
2. 如果需要特效，在 `fx_layers` 里返回特效层定义。
3. 运行生成器，检查 `out/contact_sheet.png`。
4. 在 `firmware/main/hal/hal_mcp.cpp` 里，把新名字加进 `self.robot.set_character` 的工具说明，方便模型知道有这个角色。
5. 编译、刷机，然后说"换成 XXX"。

<a id="技能图标"></a>
### 加一个技能图标

1. 在 `ICONS` 里加上 `键名: (环颜色, 绘制函数)`，然后重新生成素材。
2. 在 `firmware/main/hal/board/stackchan_display.cc` 的 `skill_icon()` 里，加上"工具名包含什么就用哪个图标"的规则。

## 同人素材声明

5 个宝可梦角色的素材属于非官方、非商业的同人作品，详见仓库根目录的 [DISCLAIMER.md](../../DISCLAIMER.md)。框架代码和技能图标是 PokeChan 的原创内容，按 MIT 许可证开源。
