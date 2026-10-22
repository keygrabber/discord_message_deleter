#!/usr/bin/env python3
"""FreeRedact launcher: run `python freeredact.py` to open the GUI.

WARNING: automating a user account (e.g. a Discord user token) can violate the
platform's Terms of Service. Use at your own risk and never share your tokens.

Hyprland - to open the window floating and centered, add to
~/.config/hypr/hyprland.conf:

    windowrulev2 = float, class:^(FreeRedact)$
    windowrulev2 = center, class:^(FreeRedact)$
    windowrulev2 = size 1020 780, class:^(FreeRedact)$
"""

from freeredact_app.gui import main

if __name__ == "__main__":
    main()
