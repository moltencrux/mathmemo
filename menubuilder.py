import logging

from PyQt5.QtWidgets import QMenu, QAction, QActionGroup
from collections.abc import Iterable


def build_menu_old(struct, group:QActionGroup=None, checkable:bool=True):
    menu = QMenu()
    for title, data in struct:
        if isinstance(data, (tuple, list)):
            submenu = build_menu(data, group)
            submenu.setTitle(title)
            menu.addMenu(submenu)
        else:
            action = menu.addAction(title)
            action.triggered.connect(item)
            if group is not None:
                group.addAction(action)

    return menu

def build_menu(struct, group:QActionGroup=None, checkable:bool=False, enabled=True):
    # builds a QMenu from a nested structure of lists or tuples.  The format is
    # ('Menu Label', data), or ('Submenu label' (('submenu item label', data), ...)

    top_level = QMenu()
    menu = top_level

    stack = list(struct)
    # This while loop flattens the nested structured menu definition.  Using a stack makes
    # recursion unnecessary here.
    while stack:
        header, data = stack.pop(0)
        if isinstance(data, (list, tuple)):
            if isinstance(header, str):
                submenu = menu.addMenu(header)
                submenu.setEnabled(enabled)
                stack.append((submenu, None))
                stack.extend(data)

        elif data is None:
            menu = header
        else:
            action = menu.addAction(header)
            action.setEnabled(enabled)
            action.setCheckable(checkable)
            action.setData(data)
            if group:
                group.addAction(action)


    return top_level



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


#context menu
    #calls copy action directoy
#copy profile config
    #checkable=True
    #changes a setting
#drag profile config
    #checkable=True
    #changes a setting

