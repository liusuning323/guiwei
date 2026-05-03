#!/bin/bash
# 归位 - 构建脚本
# 从源码构建 macOS .app 应用包
# 用法: ./build.sh

set -e

APP_NAME="归位"
VERSION="4.0"
DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD="$DIR/build"
SRC="$DIR/src"
ASSETS="$DIR/assets"

echo "构建 $APP_NAME v$VERSION ..."

# 1. 创建 .app 包结构
rm -rf "$BUILD"
mkdir -p "$BUILD/$APP_NAME.app/Contents/MacOS"
mkdir -p "$BUILD/$APP_NAME.app/Contents/Resources"

# 2. Info.plist
cat > "$BUILD/$APP_NAME.app/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>$APP_NAME</string>
    <key>CFBundleIdentifier</key>
    <string>com.suning.guiwei</string>
    <key>CFBundleName</key>
    <string>$APP_NAME</string>
    <key>CFBundleDisplayName</key>
    <string>$APP_NAME</string>
    <key>CFBundleVersion</key>
    <string>$VERSION</string>
    <key>CFBundleShortVersionString</key>
    <string>$VERSION</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleIconFile</key>
    <string>$APP_NAME</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>LSUIElement</key>
    <false/>
    <key>CFBundleDocumentTypes</key>
    <array>
        <dict>
            <key>CFBundleTypeName</key>
            <string>所有文件</string>
            <key>LSHandlerRank</key>
            <string>Default</string>
            <key>LSItemContentTypes</key>
            <array>
                <string>public.data</string>
            </array>
        </dict>
    </array>
</dict>
</plist>
EOF

# 3. 构建图标
python3 "$ASSETS/generate_icon.py"

# 4. 可执行入口
cat > "$BUILD/$APP_NAME.app/Contents/MacOS/$APP_NAME" << 'SCRIPT'
#!/bin/bash
DIR="$(cd "$(dirname "$0")/../Resources" && pwd)"
cd "$DIR"
ARGS=""
for f in "$@"; do ARGS="$ARGS '$f'"; done
if [ -n "$ARGS" ]; then
    osascript -e "tell application \"Terminal\" to activate" \
              -e "tell application \"Terminal\" to do script \"cd '$DIR' && clear && echo '归位 · 万物归其所' && echo '' && python3 归位.py $ARGS\""
else
    osascript -e "tell application \"Terminal\" to activate" \
              -e "tell application \"Terminal\" to do script \"cd '$DIR' && clear && echo '归位 · 万物归其所' && echo '' && python3 归位.py\""
fi
SCRIPT
chmod +x "$BUILD/$APP_NAME.app/Contents/MacOS/$APP_NAME"

# 5. 核心 Python 脚本
cp "$SRC/归位.py" "$BUILD/$APP_NAME.app/Contents/Resources/"

# 6. 图标
cp "$ASSETS/$APP_NAME.icns" "$BUILD/$APP_NAME.app/Contents/Resources/"

echo ""
echo "✅ 构建完成: $BUILD/$APP_NAME.app"
echo "   直接拖入 /Applications 即可安装"
