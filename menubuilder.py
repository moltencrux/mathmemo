import logging

from PyQt5.QtWidgets import QMenu, QAction, QActionGroup
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


def disable_unused_submenus(menu:QMenu):
    all_subitems_disabled = True
    logging.debug('menu has {} items'.format(len(menu.actions())))
    for action in menu.actions():
        logging.debug("checking...")
        try:
            logging.debug('checking item: {}'.format(len(action.title())))
        except AttributeError:
           pass
        if action.menu():
            logging.debug('found menu, recursing')
            disable_unused_submenus(action.menu())
            if action.menu().isEnabled():
                all_subitems_disabled = False
            else:
                action.setDisabled(True)
                logging.debug('submenu disabled')
        if isinstance(action, QAction):
            if action.isEnabled() and not action.isSeparator():
                logging.debug('found enabled item {}'.format(action.text()))
                logging.debug('has type {}'.format(type(action)))
                all_subitems_disabled = False
    if all_subitems_disabled:
        logging.debug('disabling submenu {}'.format(menu.title()))
        menu.setDisabled(True)
    else:
        logging.debug('keeping submenu {}'.format(menu.title()))
