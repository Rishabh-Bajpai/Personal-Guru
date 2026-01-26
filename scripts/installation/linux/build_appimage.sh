#!/bin/bash
set -e

# Resolve project root
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
PROJECT_ROOT="$(dirname "$(dirname "$(dirname "$SCRIPT_DIR")")")"
cd "$PROJECT_ROOT"

APP_NAME="PersonalGuru"
BUILD_DIR="AppDir"
DIST_DIR="dist"
ICON_SOURCE="app/static/favicon_io/android-chrome-512x512.png"
DESKTOP_FILE="PersonalGuru.desktop"

# Ensure clean slate
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/usr/bin"
mkdir -p "$BUILD_DIR/usr/share/icons/hicolor/512x512/apps"

# Step 1: Build the binary using the updated path
echo "Building main binary..."
"$SCRIPT_DIR/build_linux.sh"

# Step 2: Copy binary and libs to AppDir
echo "Setting up AppDir..."
cp -r "$DIST_DIR/$APP_NAME/"* "$BUILD_DIR/usr/bin/"

# Step 3: Create AppRun
cat > "$BUILD_DIR/AppRun" <<EOF
#!/bin/bash
HERE="\$(dirname "\$(readlink -f "\${0}")")"
export PATH="\${HERE}/usr/bin:\${PATH}"
export LD_LIBRARY_PATH="\${HERE}/usr/lib:\${LD_LIBRARY_PATH}"
exec PersonalGuru "\$@"
EOF
chmod +x "$BUILD_DIR/AppRun"

# Step 4: Create Desktop Entry
cat > "$BUILD_DIR/$DESKTOP_FILE" <<EOF
[Desktop Entry]
Name=$APP_NAME
Exec=PersonalGuru
Icon=$APP_NAME
Type=Application
Categories=Education;
Comment=Your Personal Guru Application
Terminal=true
EOF

# Step 5: Handle Icon
if [ -f "$ICON_SOURCE" ]; then
    cp "$ICON_SOURCE" "$BUILD_DIR/$APP_NAME.png"
    cp "$ICON_SOURCE" "$BUILD_DIR/usr/share/icons/hicolor/512x512/apps/$APP_NAME.png"
else
    echo "Warning: Icon not found at $ICON_SOURCE. Creating a dummy icon."
    touch "$BUILD_DIR/$APP_NAME.png"
fi

# Step 6: Download AppImageTool (to dist or temp, don't clutter root if possible, but keeping simpler logic for now)
APPIMAGETOOL="appimagetool-x86_64.AppImage"
if [ ! -f "$APPIMAGETOOL" ]; then
    echo "Downloading appimagetool..."
    wget -q https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x "$APPIMAGETOOL"
fi

# Step 7: Build AppImage (Using --appimage-extract-and-run if we are in Docker might be needed, but harmless outside)
echo "Generating AppImage..."
# Check if running in Docker (often useful check, but we can just run it)
./"$APPIMAGETOOL" --comp zstd --mksquashfs-opt -root-owned --no-appstream "$BUILD_DIR" "$DIST_DIR/$APP_NAME-x86_64.AppImage"

echo "Success! AppImage created at $DIST_DIR/$APP_NAME-x86_64.AppImage"
