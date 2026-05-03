#!/usr/bin/env python3
"""归位 - 图标生成器"""
from PIL import Image, ImageDraw

def generate_icon(output_path, size=1024):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 蓝色圆角背景
    bg = (55, 138, 221)
    margin = int(size * 0.04)
    draw.rounded_rectangle([margin, margin, size-margin, size-margin],
                           radius=int(size*0.18), fill=bg)

    # 白色文件夹
    fx, fy = int(size*0.22), int(size*0.31)
    fw, fh = int(size*0.57), int(size*0.43)
    white = (255, 255, 255, 255)
    draw.rounded_rectangle([fx+int(size*0.05), fy-int(size*0.06),
                            fx+int(size*0.2), fy+int(size*0.01)], radius=int(size*0.02), fill=white)
    draw.rounded_rectangle([fx, fy, fx+fw, fy+fh], radius=int(size*0.04), fill=white)
    draw.rounded_rectangle([fx+int(size*0.02), fy+int(size*0.02),
                            fx+fw-int(size*0.02), fy+fh-int(size*0.02)],
                           radius=int(size*0.02), fill=(240, 240, 245, 255))

    # 向下箭头
    cx, cy = size//2, size//2 + int(size*0.03)
    aw = int(size*0.008)
    draw.rounded_rectangle([cx-aw//2, cy-int(size*0.08), cx+aw//2, cy+int(size*0.08)],
                           radius=aw, fill=bg)
    draw.polygon([(cx, cy+int(size*0.12)), (cx-int(size*0.05), cy+int(size*0.05)),
                  (cx+int(size*0.05), cy+int(size*0.05))], fill=bg)

    # 底部目标横线
    lx, ly = cx-int(size*0.14), cy+int(size*0.15)
    draw.rounded_rectangle([lx, ly, lx+int(size*0.28), ly+int(size*0.012)],
                           radius=int(size*0.006), fill=bg)
    draw.ellipse([cx-int(size*0.015), ly-int(size*0.015),
                  cx+int(size*0.015), ly+int(size*0.015)], fill=(255, 255, 255, 255))

    img.save(output_path, 'PNG')
    return img


if __name__ == '__main__':
    import os, sys
    out_dir = os.path.dirname(os.path.abspath(__file__))
    img_1024 = os.path.join(out_dir, 'icon_1024.png')
    iconset = os.path.join(out_dir, '归位.iconset')

    generate_icon(img_1024)
    print(f'1024px 图标已生成')

    # 生成 iconset
    os.makedirs(iconset, exist_ok=True)
    img = Image.open(img_1024)
    for s in [16, 32, 128, 256, 512]:
        img.resize((s, s), Image.LANCZOS).save(os.path.join(iconset, f'icon_{s}x{s}.png'))
        img.resize((s*2, s*2), Image.LANCZOS).save(os.path.join(iconset, f'icon_{s}x{s}@2x.png'))
    img.resize((1024, 1024), Image.LANCZOS).save(os.path.join(iconset, 'icon_512x512@2x.png'))

    # 转为 .icns
    icns_out = os.path.join(out_dir, '归位.icns')
    if os.system(f'iconutil -c icns "{iconset}" -o "{icns_out}"') == 0:
        print(f'✅ .icns 图标已生成')
        # 清理临时文件
        for f in [img_1024, iconset]:
            os.system(f'rm -rf "{f}"')
