import logging
from importlib.resources import files
from pathlib import Path
from PyQt6 import uic


def pathhelper(resource, package='ui'):
    """Helper to resolve resource paths for the ui package."""
    return Path(files(package) / resource)


def load_ui_class(ui_filename, ui_class_name, generated_py_name=None):
    """
    Load a UI class dynamically based on whether the .ui file is newer than the generated .py.

    If the .ui file is newer (or the generated .py is missing), compile and load the .ui
    via uic.loadUiType. Otherwise import the pre-generated module.

    Args:
        ui_filename (str): Name of the .ui file (e.g., 'mathmemo.ui')
        ui_class_name (str): Name of the UI class (e.g., 'Ui_MainWindow')
        generated_py_name (str, optional): Explicit name of the generated .py file
            (without path). Defaults to ``{stem}_ui.py`` derived from ui_filename.

    Returns:
        type: The UI class (either from uic.loadUiType or an imported module)
    """
    ui_path = pathhelper(ui_filename)

    if generated_py_name is None:
        stem = ui_filename.rsplit('.', 1)[0]
        generated_py_name = f"{stem}_ui.py"

    ui_py_path = pathhelper(generated_py_name)

    try:
        ui_mtime = ui_path.stat().st_mtime
        py_mtime = ui_py_path.stat().st_mtime if ui_py_path.exists() else 0
        is_ui_newer = ui_mtime > py_mtime
    except FileNotFoundError:
        is_ui_newer = True
        logging.debug("No generated .py file found for %s, loading .ui directly", ui_filename)

    if is_ui_newer:
        logging.debug("Loading UI file directly: %s", ui_filename)
        # Resource module (mathmemo_rc) must already be imported by the caller.
        return uic.loadUiType(ui_path)[0]
    else:
        logging.debug("Loading generated file: %s", ui_py_path)
        module = __import__(f"ui.{ui_py_path.stem}", fromlist=[ui_class_name])
        return getattr(module, ui_class_name)


# Convenience mappings: logical name -> (ui_filename, ui_class_name, optional generated_py)
# Generated names follow build.sh conventions.
UI_CLASSES = {
    'MainWindow': ('mathmemo.ui', 'Ui_MainWindow', 'mainwindow_ui.py'),
    'Settings': ('settings.ui', 'Ui_settings', 'settings_ui.py'),
    'FormulaEdit': ('formulaedit.ui', 'Ui_FormulaEdit', 'formulaedit_ui.py'),
}
