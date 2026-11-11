import os

import mesa

MESA_TMP_FOLDER = os.path.expanduser(
    os.environ.get(
        "MESA_TMP_FOLDER", os.path.join(mesa.__path__[0], "sim", "tmp")
    )
)

# SPACEMOUSE_PRODUCT_ID = 50734
SPACEMOUSE_PRODUCT_ID = 50741 ## uncomment for older model
