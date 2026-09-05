import os
from typing import List


def find_cfg(sibling_dirs: List[str] = None) -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    # 1. LarcCommon (master config, shared by all apps)
    master = os.path.normpath(os.path.join(here, '..', 'config.ini'))
    if os.path.isfile(master):
        return master
    # 2. Current working directory
    cwd_cfg = os.path.normpath(os.path.join(os.getcwd(), 'config.ini'))
    if os.path.isfile(cwd_cfg):
        return cwd_cfg
    # 3. Sibling projects (fallback for dev)
    if sibling_dirs is None:
        sibling_dirs = ['eLarcProfPy', 'LarcSecretaire']
    for d in sibling_dirs:
        p = os.path.normpath(os.path.join(here, '..', '..', d, 'config.ini'))
        if os.path.isfile(p):
            return p
    # 4. Default (even if doesn't exist — Database will use built-in defaults)
    return master
