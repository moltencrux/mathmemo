#!/bin/sh
# compiles the UI and resource files from their definitions
pyside6-rcc -o ui/mathmemo_rc.py ui/mathmemo.qrc
# pyside6-rcc emits PySide6 imports; rewrite for PyQt6
sed -i 's/PySide6/PyQt6/g' ui/mathmemo_rc.py
pyuic6 -o ui/mainwindow_ui.py ui/mathmemo.ui
pyuic6 -o ui/settings_ui.py ui/settings.ui
pyuic6 -o ui/formulaedit_ui.py ui/formulaedit.ui
