---
name: my-wardrobe
description: 我的衣橱——衣橱单品拍照建档与杂志拼贴风「搭配样式卡」生成。当用户拍摄或上传衣服、裤子、裙子、鞋子、包包、帽子、首饰、袜子、丝巾等穿搭单品的照片,希望抠图建档、AI 美化去皱、挑选搭配、生成白底杂志拼贴风 OOTD 搭配卡(小红书竖版/公众号风)时使用。触发词:我的衣橱、搭配卡、穿搭卡、OOTD、今日穿搭、单品抠图、衣橱、衣帽间、outfit、wardrobe、搭配样式卡、帮我搭配、穿搭拼贴。
---

# 我的衣橱(My Wardrobe)· 搭配样式卡

把用户的单品照片变成白底立体单品图,挑选搭配后合成杂志拼贴风搭配卡。
视觉基准:`assets/reference-xhs-card.jpg`(小红书竖版)与
`assets/reference-card.jpeg`(经典带标签版)。

## 工作流

### 1. 录入单品

对用户上传的每张单品照片:

1. 识别槽位与档案字段(slot / label / color / style),规则见
   [references/categories.md](references/categories.md)
2. 抠图:
   - 先试 `python3 scripts/remove_bg.py <照片> -d items/`(需 `pip install rembg`)
   - 不可用时走备选方案,见 [references/style-guide.md](references/style-guide.md)「抠图备选」
3. 抠图存为透明底 PNG,统一放进工作目录的 `items/`
4. **美化(去皱板正)**:让拍出来的衣服褶皱少、整洁板正,呈电商平铺 catalog 质感
   - 首选 **AI 重绘**(效果好一个量级):用图像生成工具 image-to-image,
     透明底 + 1:1,prompt 模板:

     ```
     Professional e-commerce flat-lay product photo of the exact same
     {单品描述} from the reference image, faithfully preserving its color,
     print pattern, and silhouette. Neatly pressed, no wrinkles, symmetrical
     flat lay on transparent background, soft studio lighting, high detail.
     ```

     注意:
     - 单品形态易漂移时(连衣裙/连体裤等)在 prompt 里写死结构,如
       "DRESS with continuous flared SKIRT hem, not a romper, not shorts,
       no leg openings"
     - 遇到限流(HTTP 424)就 sleep 20–30 秒后重试同一件
     - **逐件审查**重绘结果与原图的保真度(印花、领口、五金件),
       不合格的用更精确的 prompt 重绘或回退本地方案
   - 无 AI 重绘能力时回退本地脚本(对轻褶有效,深褶有限):

     ```bash
     python3 scripts/beautify_item.py items/item1.png -o items/item1.png
     ```

5. 向用户回报清单:每件一行「slot · label · 文件名」

一次录入多件时逐张处理;照片里有多个单品(如一身穿搭照)时,
先问用户要拆成几件,分别裁剪后再抠图。

### 2. 挑选搭配

列出已建档单品,请用户选择本套搭配的件数与组合。用户说「帮我搭」时:

- 按 [references/categories.md](references/categories.md) 的槽位规则组一套
  (上装/连衣裙 + 下装 + 鞋为核心,包/帽子/首饰点缀)
- 说明理由(配色、风格、场合),让用户确认或替换

### 3. 生成搭配卡

两种版式,默认用小红书竖版:

1. **小红书竖版(默认)**:`scripts/compose_card_xhs.py`
   - 1152×2048(9:16),纯白底,无单品标签,杂志剪贴感
   - 大件铺底、包压最上,单品带柔和投影 + 确定性微旋转(±3°)
   - 自动擦除 AI 美化图左下角的「AI生成」水印(见 style-guide)
   - 底部一行可选小号题注(spec 里给 `title`)
2. **经典 3:4 带标签版**:`scripts/compose_card.py`(原版式,公众号风)

执行(以小红书版为例):

```bash
python3 scripts/compose_card_xhs.py spec.json -o outfit-card.png
```

spec JSON 每项填 `image`(抠图路径)、`id`、`slot`;可加 `title`
(结构见脚本顶部 docstring)。

自检与交付:

1. 打开输出图自检,对照 [references/style-guide.md](references/style-guide.md):
   白底纯净、无水印穿帮、单品不溢出画布、层叠关系自然(包压大件上)、
   经典版额外确认标签无乱码(含中文时确认 CJK 字体生效)
2. 不满意可改 spec 重跑;布局规则需调整时直接改脚本里的 `ZONES` 表
3. 把成品图交付给用户,附单品清单

## 注意

- 脚本只依赖 Pillow;合成前 `pip install pillow` 若缺失
- 本地去皱脚本依赖 OpenCV:`pip install opencv-python-headless` 后使用
- 标签含中文时脚本会自动切换到 CJK 字体,无需干预
- 用户没有品牌信息时,label 用「品类 + 颜色」,不要编造品牌名
- 小红书版式默认 9:16(1152×2048);经典版默认 3:4,
  用户要方形/横版时改 spec 里的 `canvas`
