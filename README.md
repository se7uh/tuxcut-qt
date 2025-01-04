# TuxCut Qt

<p align="center">
  <img src="tuxcut.png" alt="TuxCut Qt Logo" width="200"/>
</p>

TuxCut Qt is a network management tool that allows you to:
- View all devices on your network
- Control network access for devices
- Change MAC address
- Manage device aliases

## Preview
<p align="center">
  <img src="https://github.com/user-attachments/assets/9f16e1cd-912d-4e3c-bded-d642f7729ba3" alt="TuxCut Qt Preview" width="800"/>
</p>

## Features
- Modern Qt6 interface
- Python 3.10+ support
- Easy to use network management
- Device aliasing support
- MAC address spoofing
- Network protection mode

## Requirements
- Python 3.10 or higher
- Root/sudo privileges
- Linux system with NetworkManager

## Installation

### From Packages
Download the latest RPM or DEB package from the [Releases](https://github.com/se7uh/tuxcut-qt/releases) page.

For RPM-based distributions (Fedora, RHEL, etc.):
```bash
sudo rpm -i tuxcut-qt-*.rpm
```

For DEB-based distributions (Ubuntu, Debian, etc.):
```bash
sudo dpkg -i tuxcut-qt-*.deb
```

### From Source
1. Clone the repository:
```bash
git clone https://github.com/se7uh/tuxcut-qt
cd tuxcut-qt
```

2. Create and activate virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the application:
```bash
sudo .venv/bin/python client/tuxcut_qt.py
```

### Build RPM/DEB Package
You can build RPM or DEB packages using the build script:

```bash
./build.sh rpm  # For RPM package
./build.sh deb  # For DEB package
```

The built packages will be available in the `dist` directory.

## Usage
1. Launch TuxCut Qt with root privileges
2. The application will scan your network and display connected devices
3. Select a device from the list to:
   - Cut its network access
   - Resume its network access
   - Give it an alias
   - Change its MAC address
4. Use the protection mode to prevent others from cutting your connection

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## License
This project is licensed under GPL v3 - see the LICENSE file for details.

## Authors
- Original author: a-talla
- Qt port: se7uh
