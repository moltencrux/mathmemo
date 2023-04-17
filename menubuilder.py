from PyQt5.QtWidgets import QMenu, QActionGroup
from collections.abc import Iterable


def build_menu(struct, group:QActionGroup=None, checkable:bool=True):
    menu = QMenu()
    for title, item in struct:
        if isinstance(item, tuple) or isinstance(item, list):
            submenu = build_menu(item, group)
            submenu.setTitle(title)
            menu.addMenu(submenu)
        else:
            action = menu.addAction(title)
            action.triggered.connect(item)
            if group is not None:
                group.addAction(action)

    return menu