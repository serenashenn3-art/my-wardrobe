#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小红书风搭配卡合成(杂志拼贴感,无标签,层叠+轻投影+微旋转)

用法:
    python3 compose_card_xhs.py spec.json -o outfit.png

spec JSON:
{
  "title": "法式复古通勤",           # 可选,底部小号衬线题注;留空则不画
  "canvas": [1152, 2048],            # 可选,默认 1152x2048(9:16 竖版)
  "items": [
    {"image": "items/item15.png", "label": "藏蓝印花裙", "slot": "dress"},
    ...
  ]
}

单品可选 "layout" 字段(Widget 拖拽定稿时传入):
  {"x": 0.30, "y": 0.45, "h": 0.38, "rot": -2.0, "z": 7}
  x,y  = 中心点(画布比例坐标); h = 单品高度占画幅比例;
  rot  = 旋转角度(度,替代默认哈希微旋转); z = 层叠顺序(越大越靠上)
带 layout 的单品跳过 ZONES 自动摆位,按给定参数精确落位。

与 compose_card.py 的区别:
- 画布 9:16 竖版,纯白底,单品之间刻意层叠(大件铺底、包压最上)
- 无文字标签;单品带柔和投影与确定性微旋转,呈杂志剪贴感
- 仅底部一行小号题注(可选)
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

CANVAS = (1152, 2048)
BG = (255, 255, 255, 255)

# 槽位 -> 默认摆放盒 (x0, y0, x1, y1), 画布比例坐标
ZONES = {
    "dress":     (0.00, 0.00, 0.68, 0.58),
    "top":       (0.00, 0.00, 0.64, 0.54),
    "outerwear": (0.00, 0.02, 0.62, 0.56),
    "bottom":    (0.52, 0.14, 1.00, 0.97),
    "shoes":     (0.02, 0.64, 0.48, 0.99),
    "bag":       (0.24, 0.36, 0.92, 0.74),
    "hat":       (0.62, 0.01, 0.99, 0.15),
    "jewelry":   (0.62, 0.03, 0.99, 0.19),
    "scarf":     (0.60, 0.20, 0.98, 0.38),
    "socks":     (0.55, 0.72, 0.75, 0.90),
    "accessory": (0.60, 0.20, 0.98, 0.36),
}
# 槽位 -> 摆放盒填充比例(越大越压出盒外,增强大小对比)
FILLS = {"dress": 1.0, "outerwear": 1.0, "bottom": 0.98, "bag": 1.04,
         "shoes": 0.94, "hat": 0.9, "jewelry": 0.88}
# 绘制顺序: 先铺大件,包最后压在最上层
PAINT_ORDER = ["bottom", "dress", "top", "outerwear", "scarf",
               "shoes", "socks", "hat", "jewelry", "accessory", "bag"]
# 同角落冲突时的盒微调: hat+jewelry 同时在场, jewelry 下移
JITTER_SEED_SALT = "outfit-xhs-v1"


def trim_alpha(im: Image.Image) -> Image.Image:
    bbox = im.split()[-1].getbbox()
    return im.crop(bbox) if bbox else im


def erase_watermark(im: Image.Image) -> Image.Image:
    """擦除 AI 生图左下角的「AI生成」半透明水印。

    水印特征固定: 位于左下角落(x<24%, y>83%), 近白灰色(200-245),
    半透明(alpha 40-235)。衣服本体即使白色也多为不透明(alpha 255),
    且单品主体居中、一般不伸进该角落,误伤风险极低。
    """
    w, h = im.size
    px = im.load()
    for y in range(int(h * 0.83), h):
        for x in range(int(w * 0.24)):
            r, g, b, a = px[x, y]
            if 40 < a < 235 and r > 190 and g > 190 and b > 190:
                px[x, y] = (r, g, b, 0)
    return im


def soft_shadow(im: Image.Image, blur=18, dy=16, opacity=90) -> Image.Image:
    """返回比原图稍大的 RGBA 图: 阴影+本体。"""
    pad = blur * 2
    canvas = Image.new("RGBA", (im.width + pad * 2, im.height + pad * 2 + dy), (0, 0, 0, 0))
    alpha = im.split()[-1].point(lambda a: a * opacity // 255)
    shadow = Image.new("RGBA", im.size, (30, 25, 20, 255))
    shadow.putalpha(alpha)
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
    canvas.paste(shadow, (pad, pad + dy), shadow)
    canvas.paste(im, (pad, pad), im)
    return canvas


def rotation_for(item_id: str) -> float:
    h = hashlib.md5((JITTER_SEED_SALT + item_id).encode()).digest()[0]
    return (h / 255.0 - 0.5) * 6.0  # -3° ~ +3°


def load_font(size: int):
    for p in ["/System/Library/Fonts/PingFang.ttc",
              "/System/Library/Fonts/STHeiti Light.ttc"]:
        if Path(p).exists():
            for idx in (2, 0, 1):  # 优先细体,失败回退常规体
                try:
                    return ImageFont.truetype(p, size, index=idx)
                except (OSError, IOError):
                    continue
    return ImageFont.load_default()


def fit_box(im: Image.Image, box, W, H, fill=0.96):
    x0, y0, x1, y1 = box
    bw, bh = (x1 - x0) * W * fill, (y1 - y0) * H * fill
    scale = min(bw / im.width, bh / im.height)
    nw, nh = int(im.width * scale), int(im.height * scale)
    im = im.resize((nw, nh), Image.LANCZOS)
    cx, cy = (x0 + x1) / 2 * W, (y0 + y1) / 2 * H
    return im, int(cx - nw / 2), int(cy - nh / 2)


def compose(spec: dict, out_path: str):
    W, H = spec.get("canvas", CANVAS)
    canvas = Image.new("RGBA", (W, H), BG)

    items = list(spec.get("items", []))
    slots_present = {it.get("slot") for it in items}

    def zone_of(slot):
        box = ZONES.get(slot, ZONES["accessory"])
        if slot == "jewelry" and "hat" in slots_present:
            box = (0.62, 0.15, 0.99, 0.30)
        if slot == "hat" and "jewelry" not in slots_present:
            box = ZONES["hat"]
        return box

    def paint_key(it):
        lay = it.get("layout") or {}
        if isinstance(lay.get("z"), (int, float)):
            return (1, lay["z"])
        slot = it.get("slot", "accessory")
        return (0, PAINT_ORDER.index(slot) if slot in PAINT_ORDER else len(PAINT_ORDER))

    ordered = sorted(items, key=paint_key)

    for it in ordered:
        path = it["image"]
        im = Image.open(path).convert("RGBA")
        im = erase_watermark(im)
        im = trim_alpha(im)
        lay = it.get("layout") or {}
        if isinstance(lay.get("h"), (int, float)) and lay["h"] > 0:
            # 拖拽定稿模式: 按 Widget 传来的比例参数精确落位
            scale = lay["h"] * H / im.height
            nw = max(1, int(im.width * scale))
            nh = max(1, int(im.height * scale))
            im = im.resize((nw, nh), Image.LANCZOS)
            x = int(lay.get("x", 0.5) * W - nw / 2)
            y = int(lay.get("y", 0.5) * H - nh / 2)
            ang = float(lay.get("rot", 0.0))
        else:
            box = zone_of(it.get("slot", "accessory"))
            fill = FILLS.get(it.get("slot", "accessory"), 0.96)
            im, x, y = fit_box(im, box, W, H, fill=fill)
            ang = rotation_for(it.get("id") or it.get("label") or path)
        im = soft_shadow(im)
        bw, bh = im.width, im.height
        im = im.rotate(-ang, expand=True, resample=Image.BICUBIC)
        x -= (im.width - bw) // 2   # 旋转膨胀后保持中心不动
        y -= (im.height - bh) // 2
        canvas.paste(im, (x, y), im)

    title = (spec.get("title") or "").strip()
    if title:
        draw = ImageDraw.Draw(canvas)
        font = load_font(int(H * 0.017))
        text = title
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) / 2, H * 0.965), text, fill=(150, 142, 128), font=font)

    canvas.convert("RGB").save(out_path, quality=95)
    print(f"已生成: {out_path} ({W}x{H}, {len(items)} 件单品)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("-o", "--output", default="outfit-card-xhs.png")
    args = ap.parse_args()
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    compose(spec, args.output)


if __name__ == "__main__":
    main()
