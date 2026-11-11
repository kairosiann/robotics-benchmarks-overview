"""
This script sets up a private macros file.
The private macros file (macros_private.py) is not tracked by git,
allowing user-specific settings that are not tracked by git.
This script checks if macros_private.py exists.
If applicable, it creates the private macros at robosuite/macros_private.py
"""

import os
import re
import shutil

import robosuite

if __name__ == "__main__":
    base_path = robosuite.__path__[0]
    macros_path = os.path.join(base_path, "macros.py")
    macros_private_path = os.path.join(base_path, "macros_private.py")

    if not os.path.exists(macros_path):
        print("{} does not exist! Aborting...".format(macros_path))

    if os.path.exists(macros_private_path):
        with open(macros_private_path, "r", encoding="utf-8") as f:
            if re.search(r'^IMAGE_CONVENTION\s*=\s*"opencv"', f.read(), flags=re.MULTILINE):
                print("{} already sets IMAGE_CONVENTION = \"opencv\"; nothing to do.".format(macros_private_path))
                exit()
        ans = input("{} already exists! \noverwrite? (y/n)\n".format(macros_private_path))

        if ans == "y":
            print("REMOVING")
        else:
            exit()

    shutil.copyfile(macros_path, macros_private_path)
    with open(macros_private_path, "r", encoding="utf-8") as f:
        macros_private = f.read()

    macros_private = re.sub(
        r'^(IMAGE_CONVENTION\s*=\s*)"[^"]+"(\s*#.*)?$',
        r'\1"opencv"\2',
        macros_private,
        flags=re.MULTILINE,
    )

    with open(macros_private_path, "w", encoding="utf-8") as f:
        f.write(macros_private)

    print("copied {}\nto {}".format(macros_path, macros_private_path))
