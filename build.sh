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

# Copy files
cp -r client server requirements.txt tuxcut.png "$STAGING/$INSTALL_DIR/"
cp -r .venv "$STAGING/$INSTALL_DIR/"

# Create launcher script
cat > "$STAGING/$BIN_DIR/tuxcut-qt" << 'EOF'
#!/bin/bash
sudo /opt/tuxcut-qt/.venv/bin/python /opt/tuxcut-qt/client/tuxcut_qt.py
EOF
chmod +x "$STAGING/$BIN_DIR/tuxcut-qt"

# Function to build packages
build_package() {
    local TYPE=$1
    local ARCH="x86_64"
    local DEPS="python3 >= 3.10"
    
    echo "Building $TYPE package..."
    
    fpm -s dir -t $TYPE \
        -n "tuxcut-qt" \
        -v $VERSION \
        --description "$DESCRIPTION" \
        --url "$URL" \
        --maintainer "$MAINTAINER" \
        --license "$LICENSE" \
        --depends "$DEPS" \
        -a $ARCH \
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

echo "Done! Package is available in the dist directory."
