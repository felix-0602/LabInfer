#!/usr/bin/env bash
# 重新生成 design/assets/ 下的 GEN 素材（Blender 渲染 + ImageMagick 后处理）。
#
# 依赖：Blender ≥ 4.2（Cycles，有 NVIDIA 显卡时自动用 OptiX），ImageMagick 7。
# 用法：
#   BLENDER=/path/to/blender ./render.sh            # 全部
#   BLENDER=/path/to/blender ./render.sh GEN-03     # 只出一张
#   QUICK=1 ./render.sh                             # 低采样快速预览
set -euo pipefail
cd "$(dirname "$0")"
BLENDER=${BLENDER:-blender}
OUT=../assets
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$OUT"

want() { [ $# -eq 0 ] || [[ " $* " == *" $ID "* ]]; }
samples() { [ -n "${QUICK:-}" ] && echo $(( $1 / 8 )) || echo "$1"; }

render() { # script w h samples [extra]
  "$BLENDER" -b --factory-startup -P "$1" -- "$TMP/$ID.png" "$2" "$3" "$(samples "$4")" "${5:-}" 2>&1 \
    | grep -E "Saved|Error|Traceback" || true
}

grain() { # 在 50% 灰上加高斯噪声，再用叠加模式压到图上，得到中性的胶片颗粒
  local size; size=$(magick identify -format "%wx%h" "$1")
  magick "$1" \( -size "$size" xc:gray50 -seed 7 -attenuate "$2" +noise Gaussian -colorspace Gray \) \
    -compose Overlay -composite "$1"
}

ARGS=("$@")
for ID in GEN-01 GEN-02 GEN-03 GEN-04 GEN-05; do
  want "${ARGS[@]}" || continue
  echo "== $ID"
  case $ID in
    GEN-01) render tube.py 1400 1800 512
            magick "$TMP/$ID.png" -quality 90 -define webp:alpha-quality=100 "$OUT/$ID.webp" ;;
    GEN-02) render smoke.py 2880 1800 16 night
            grain "$TMP/$ID.png" 0.5
            magick "$TMP/$ID.png" -quality 86 "$OUT/$ID.webp" ;;
    GEN-03) render orb.py 1000 1000 384
            magick "$TMP/$ID.png" -quality 90 -define webp:alpha-quality=100 "$OUT/$ID.webp" ;;
    GEN-04) render shards.py 2040 450 384
            magick "$TMP/$ID.png" -level 0%,90% -quality 88 "$OUT/$ID.webp" ;;
    GEN-05) render smoke.py 2880 1800 16 day
            grain "$TMP/$ID.png" 0.35
            magick "$TMP/$ID.png" -quality 86 "$OUT/$ID.webp" ;;
  esac
done
ls -la "$OUT"
