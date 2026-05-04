#!/usr/bin/env python3
"""
TN Election 2026 Monitor - Launcher & Dependency Installer
This script checks for required packages, installs missing ones, and launches the main application.
Run: python launch_app.py
"""

import subprocess
import sys
import os
import importlib.metadata
from pathlib import Path

# Required packages with minimum versions
REQUIRED_PACKAGES = {
    "requests": "2.31.0",
    "beautifulsoup4": "4.12.0",
    "ttkbootstrap": "1.10.0",
    "matplotlib": "3.7.0",
    "reportlab": "4.0.0",
    "numpy": "1.24.0",
    "Pillow": "10.0.0",
    "lxml": "4.9.0",
    "certifi": "2023.0.0",
    "urllib3": "2.0.0",
    "charset-normalizer": "3.0.0",
}

# Optional packages (nice to have but not critical)
OPTIONAL_PACKAGES = {
    "pyinstaller": "6.0.0",  # For building EXE
}


def get_installed_version(package_name):
    """Get installed version of a package."""
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return None


def install_package(package_name, min_version=None):
    """Install a package using pip."""
    version_spec = f">={min_version}" if min_version else ""
    package_spec = f"{package_name}{version_spec}"
    
    print(f"  📦 Installing {package_spec}...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", package_spec, "--quiet", "--upgrade"],
            check=True,
            capture_output=True,
            text=True
        )
        print(f"  ✓ {package_name} installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ✗ Failed to install {package_name}: {e}")
        return False


def check_and_install():
    """Check all required packages and install missing ones."""
    print("=" * 70)
    print("  TN Election 2026 Monitor - Dependency Checker & Launcher")
    print("=" * 70)
    print("\n🔍 Checking required packages...\n")
    
    missing_packages = []
    outdated_packages = []
    
    for package, min_version in REQUIRED_PACKAGES.items():
        installed_version = get_installed_version(package)
        
        if installed_version is None:
            print(f"  ❌ {package} - NOT INSTALLED")
            missing_packages.append((package, min_version))
        else:
            # Simple version comparison (string comparison works for semantic versions)
            if installed_version < min_version:
                print(f"  ⚠️  {package} - version {installed_version} (need >= {min_version})")
                outdated_packages.append((package, min_version))
            else:
                print(f"  ✓ {package} - version {installed_version}")
    
    if missing_packages or outdated_packages:
        print("\n" + "=" * 70)
        print("  📦 Installing missing/updating outdated packages...")
        print("=" * 70)
        
        # Install missing packages
        for package, min_version in missing_packages:
            install_package(package, min_version)
        
        # Update outdated packages
        for package, min_version in outdated_packages:
            install_package(package, min_version)
        
        print("\n✅ All required packages are now installed!\n")
    else:
        print("\n✅ All required packages are already installed!\n")
    
    # Check optional packages (just inform, don't install automatically)
    print("📋 Optional packages (for advanced features):")
    for package, min_version in OPTIONAL_PACKAGES.items():
        installed_version = get_installed_version(package)
        if installed_version:
            print(f"  ✓ {package} - version {installed_version}")
        else:
            print(f"  ○ {package} - NOT INSTALLED (for building EXE only)")
    
    return True


def launch_app():
    """Launch the main TN Election Monitor application."""
    print("\n" + "=" * 70)
    print("  🚀 Launching TN Election 2026 Monitor...")
    print("=" * 70)
    print("\n  The application window will open shortly.")
    print("  Please wait while the interface loads...\n")
    
    # Get the directory where this script is located
    script_dir = Path(__file__).parent.resolve()
    main_script = script_dir / "tn_election_monitor.py"
    
    if not main_script.exists():
        print(f"❌ ERROR: Could not find {main_script}")
        print("   Make sure tn_election_monitor.py is in the same directory as launch_app.py")
        return False
    
    # Launch the main application
    try:
        subprocess.run([sys.executable, str(main_script)], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Application exited with error: {e}")
        return False
    except KeyboardInterrupt:
        print("\n\n👋 Application terminated by user")
        return True


def main():
    """Main entry point."""
    try:
        # Check and install dependencies
        if not check_and_install():
            print("\n❌ Failed to install required dependencies.")
            print("   Please install manually using: pip install -r requirements.txt")
            input("\nPress Enter to exit...")
            sys.exit(1)
        
        # Launch the application
        if not launch_app():
            print("\n❌ Failed to launch the application.")
            input("\nPress Enter to exit...")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        input("\nPress Enter to exit...")
        sys.exit(1)


if __name__ == "__main__":
    main()