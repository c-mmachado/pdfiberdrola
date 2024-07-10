# -*- coding: utf-8 -*-

# Python Imports
import re
from sys import argv
from typing import Dict, List

# Third-Party Imports

# Local Imports

# Constants
ENV_FILE: str = argv[1] if len(argv) > 1 else "../config/.env"
NSIS_SCRIPT: str = argv[2] if len(argv) > 2 else "../resources/installer/nsis-setup.nsi"
CONFIG_TXT: str = argv[3] if len(argv) > 3 else "../resources/installer/config.txt"

env_props: Dict[str, int] = {}
with open(ENV_FILE, 'r') as f:
    lines: List[str] = f.readlines()
    for line in lines:
        if line.startswith("APP_VERSION"):
            prop_split: List[str] = line.split("=")
            version_split: List[str] = prop_split[1].split(".")
            env_props["version_major"] = version_split[0].strip() if len(version_split) > 0 else "0"
            env_props["version_minor"] = version_split[1].strip() if len(version_split) > 1 else "0"
            env_props["version_build"] = version_split[2].strip() if len(version_split) > 2 else "0"
            env_props["version_patch"] = version_split[3].strip() if len(version_split) > 3 else None
            break

with open(NSIS_SCRIPT, 'r') as f:
    lines: List[str] = f.readlines()
    for i, line in enumerate(lines):
        if line.lower().startswith("!define"):
            line_split: List[str] = line.strip().split()
            
            if len(line_split) > 1:
                if line_split[1].lower() == "versionmajor":
                    lines[i] = f"!define VERSIONMAJOR {env_props['version_major']}\n"
                elif line_split[1].lower() == "versionminor":
                    lines[i] = f"!define VERSIONMINOR {env_props['version_minor']}\n"
                elif line_split[1].lower() == "versionbuild":
                    lines[i] = f"!define VERSIONBUILD {env_props['version_build']}\n"
                elif line_split[1].lower() == "versionpatch":
                    lines[i] = f"!define VERSIONPATCH {env_props['version_patch']}\n"
        
with open(NSIS_SCRIPT, 'w') as f:
    f.writelines(lines)
    
with open(CONFIG_TXT, 'r') as f:
    lines: List[str] = f.readlines()
    for i, line in enumerate(lines):
        line_split: List[str] = line.strip().split('=')
        
        if len(line_split) > 1:
            lines[i] = f'{line_split[0]}={re.sub(r'(v\d+(?:\.\d+)?(?:\.\d+)?(?:\.\d+)?)', 
                            f'v{env_props["version_major"]}.{env_props["version_minor"]}.{env_props["version_build"]}{'.' + env_props["version_patch"] if env_props["version_patch"] else ""}', 
                            line_split[1])}\n'

with open(CONFIG_TXT, 'w') as f:
    f.writelines(lines)