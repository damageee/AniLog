"""运行 AniLog。"""

import flet as ft

from bangumi.app import install_escape_back, main
from bangumi.core.paths import assets_directory
from bangumi.services.proxy import configure_proxy

if __name__ == "__main__":
    configure_proxy()
    assets = assets_directory()
    extra = {"assets_dir": str(assets)} if assets.is_dir() else {}
    ft.run(main, before_main=install_escape_back, **extra)
