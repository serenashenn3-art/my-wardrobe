#!/usr/bin/env python3
"""beautify_item.py — 单品抠图自动美化:减少褶皱阴影,呈现整洁板正的电商平铺感.

原理(频率分离 + 保边平滑):
- 褶皱是「低频明暗起伏」,印花/包边/钻扣是「高频细节」
- 对亮度通道做双边滤波分离低频层,压平低频起伏,保留高频细节
- 透明区域不参与计算,轮廓不受影响

用法:
    python3 beautify_item.py input.png                 # -> input_beauty.png
    python3 beautify_item.py items/*.png -d beauty/    # 批量
    python3 beautify_item.py in.png --strength 0.8     # 去皱强度 0-1,默认 0.65

依赖: numpy + scikit-image(rembg 安装时已带入). 仅处理 RGBA/透明底 PNG;
白底图会先按近白色生成 alpha 再处理。
"""

import argparse
import glob
import os
import sys

import numpy as np


def load_rgba(path):
    from PIL import Image
    img = Image.open(path).convert("RGBA")
    arr = np.asarray(img).astype(np.float32) / 255.0
    if arr[..., 3].min() > 0.98:  # 无透明信息:近白背景转 alpha
        rgb = arr[..., :3]
        alpha = 1.0 - np.clip((rgb.min(axis=-1) - 0.90) / 0.10, 0, 1)
        arr[..., 3] = alpha
    return arr


def beautify(arr, strength=0.65):
    import cv2

    rgb = (arr[..., :3] * 255).astype(np.uint8)
    alpha = arr[..., 3]
    mask = (alpha > 0.05)
    if not mask.any():
        return arr

    # LAB 亮度通道;背景填区域均值,避免边缘污染
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    L = lab[..., 0].astype(np.float32)
    fill = float(L[mask].mean())
    L_filled = np.where(mask, L, fill).astype(np.uint8)

    # 低频层:强双边滤波(褶皱=柔和明暗起伏,印花/包边=硬边被保留)
    base = cv2.bilateralFilter(L_filled, 0, 28, 30)
    flat = cv2.bilateralFilter(base, 0, 18, 45).astype(np.float32)
    base = base.astype(np.float32)

    detail = L - base
    L_new = (1 - strength) * L + strength * flat + detail * 0.6
    # 轻度提亮,接近影棚产品图的通透感
    L_new = np.clip(L_new * 1.04 + 2.0, 0, 255)

    lab[..., 0] = L_new.astype(np.uint8)
    out_rgb = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB).astype(np.float32) / 255.0
    out = arr.copy()
    out[..., :3] = np.where(mask[..., None], out_rgb, arr[..., :3])
    return out


def process(src, dst, strength):
    from PIL import Image
    arr = load_rgba(src)
    result = beautify(arr, strength)
    Image.fromarray((result * 255).astype(np.uint8), "RGBA").save(dst)
    print(f"美化完成: {dst}")


def main():
    ap = argparse.ArgumentParser(description="单品抠图去皱美化")
    ap.add_argument("inputs", nargs="+", help="PNG 路径或 glob 模式")
    ap.add_argument("-d", "--outdir", default=None,
                    help="输出目录(默认与输入同目录,加 _beauty 后缀)")
    ap.add_argument("--strength", type=float, default=0.65,
                    help="去皱强度 0-1,默认 0.65")
    args = ap.parse_args()

    files = []
    for pat in args.inputs:
        files.extend(glob.glob(pat) or [pat])
    if args.outdir:
        os.makedirs(args.outdir, exist_ok=True)

    for src in files:
        if not os.path.exists(src):
            print(f"[warn] 找不到 {src},跳过", file=sys.stderr)
            continue
        base = os.path.splitext(os.path.basename(src))[0]
        if args.outdir:
            dst = os.path.join(args.outdir, base + ".png")
        else:
            dst = os.path.join(os.path.dirname(src), base + "_beauty.png")
        try:
            process(src, dst, args.strength)
        except Exception as e:  # noqa: BLE001
            print(f"[error] {src} 美化失败: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
