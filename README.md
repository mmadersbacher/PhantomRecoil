<div align="center">
  <h1>🎮 Rainbow Six Siege - Enterprise Recoil Macro</h1>
  <p>A highly sophisticated, dynamically scaling recoil control application for Windows, featuring a 1000Hz hardware layer polling system and a modern Zinc-900 Enterprise web dashboard.</p>
</div>

## ✨ Features
- **Flawless Recoil Engine**: Sub-pixel smooth mouse logic driven natively via `ctypes` and `win32api`.
- **DPI Agnostic Math**: Built-in logic scalar perfectly adjusts X/Y curves to your exact DPI configuration.
- **Enterprise Dashboard**: A beautifully crafted flat-UI architecture inspired by top-tier developer platforms.
- **Dynamic CDN Assets**: Fetches up-to-date Operator badges and weapon silhouettes directly from the Tracker Network.
- **Zero-Click Updates**: Integrated GitHub Release API polling. Upon opening, the app automatically downloads and patches itself to the newest available executable release.
- **Hardware Sync**: Real-time physical Caps Lock polling loop seamlessly syncs your keyboard's LED status with the UI, without thread-locking. 

## 🚀 Getting Started

If you want to run the project from source:
1. Ensure Python 3.9+ is installed
2. Run `START.bat` - This automatically handles environment setup (installs `pywebview`, `pywin32`) and launches the GUI.

If you just want the executable application, check out the **[Releases](https://github.com/mmadersbacher/RainbowSixRecoil/releases)** tab!

## 🛠️ Building the Standalone `.exe`
A streamlined **`BUILD.bat`** compiler orchestrator is included. 
Double-clicking `BUILD.bat` will trigger `PyInstaller` to bundle the entire Python source, the asynchronous webhook listeners, and the embedded `web` files into a single standalone `R6_Recoil_Standalone.exe` located within the automatically generated `/dist` folder. 
