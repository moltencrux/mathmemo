#!/bin/sh

pyrcc5 -o ui/mathmemo_rc.py ui/mathmemo.qrc
pyuic5 -o ui/mainwindow_ui.py ui/mathmemo.ui --import-from=ui
pyuic5 -o ui/settings_ui.py ui/settings.ui --import-from=ui
