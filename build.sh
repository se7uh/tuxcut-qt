#!/bin/bash

# Check if FPM is installed
if ! command -v fpm &> /dev/null; then
    echo "FPM is not installed. Please install FPM first:"
    echo "gem install fpm"
    exit 1
fi

# Ensure we're in the project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
else
    source .venv/bin/activate
fi

# Create dist directory
mkdir -p dist

# Package version
VERSION="7.0"

# Common package info
MAINTAINER="se7uh"
DESCRIPTION="Network management tool for Linux"
URL="https://github.com/se7uh/tuxcut-qt"
LICENSE="GPL-3.0"

# Common directories
INSTALL_DIR="/opt/tuxcut-qt"
BIN_DIR="/usr/bin"

# Create staging area
STAGING="$(mktemp -d)"
mkdir -p "$STAGING/$INSTALL_DIR"
mkdir -p "$STAGING/$BIN_DIR"

# Build executables with PyInstaller
echo "Building executables..."
pyinstaller --clean -F \
    --add-data "tuxcut.png:." \
    --hidden-import PyQt6.QtCore \
    --hidden-import PyQt6.QtGui \
    --hidden-import PyQt6.QtWidgets \
    --collect-all PyQt6 \
    client/tuxcut_qt.py

pyinstaller --clean -F server/server.py

# Copy files to staging
cp dist/tuxcut_qt "$STAGING/$INSTALL_DIR/"
cp dist/server "$STAGING/$INSTALL_DIR/"
cp tuxcut.png "$STAGING/$INSTALL_DIR/"

# Create launcher script
cat > "$STAGING/$BIN_DIR/tuxcut-qt" << 'EOF'
#!/bin/bash
sudo /opt/tuxcut-qt/tuxcut_qt
EOF
chmod +x "$STAGING/$BIN_DIR/tuxcut-qt"

# Function to build packages
build_package() {
    local TYPE=$1
    local ARCH="x86_64"
    local DEPS=(
        "libxcb-icccm4" "libxcb-image0" "libxcb-keysyms1" "libxcb-randr0"
        "libxcb-render-util0" "libxcb-xinerama0" "libxcb-xkb1" "libxkbcommon-x11-0"
        "libxcb-shape0" "libxcb-cursor0"
    )
    
    echo "Building $TYPE package..."
    
    # Convert dependencies format based on package type
    local DEP_ARGS=""
    for dep in "${DEPS[@]}"; do
        if [ "$TYPE" = "rpm" ]; then
            # Convert debian package names to fedora equivalents
            dep=$(echo $dep | sed 's/lib\(.*\)[0-9]$/lib\1/')
        fi
        DEP_ARGS="$DEP_ARGS --depends $dep"
    done
    
    fpm -s dir -t $TYPE \
        -n "tuxcut-qt" \
        -v $VERSION \
        --description "$DESCRIPTION" \
        --url "$URL" \
        --maintainer "$MAINTAINER" \
        --license "$LICENSE" \
        -a $ARCH \
        $DEP_ARGS \
        -C "$STAGING" \
        --after-install "scripts/postinst" \
        --before-remove "scripts/prerm" \
        -p "dist/tuxcut-qt-${VERSION}-1.${ARCH}.$TYPE" \
        .
        
    if [ $? -eq 0 ]; then
        echo "$TYPE package built successfully!"
    else
        echo "Failed to build $TYPE package"
        exit 1
    fi
}

# Create post-install script
mkdir -p scripts
cat > scripts/postinst << 'EOF'
#!/bin/bash
chmod +x /usr/bin/tuxcut-qt
chmod +x /opt/tuxcut-qt/tuxcut_qt
chmod +x /opt/tuxcut-qt/server
EOF

# Create pre-remove script
cat > scripts/prerm << 'EOF'
#!/bin/bash
rm -f /usr/bin/tuxcut-qt
EOF

chmod +x scripts/postinst scripts/prerm

# Build packages based on argument
case "$1" in
    "rpm")
        build_package rpm
        ;;
    "deb")
        build_package deb
        ;;
    *)
        echo "Usage: $0 {rpm|deb}"
        exit 1
        ;;
esac

# Cleanup
rm -rf "$STAGING"
rm -rf scripts
rm -rf build
rm -rf *.spec

echo "Done! Package is available in the dist directory."
