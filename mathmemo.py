#!/usr/bin/env -S python3 -O
import logging, sys
from PyQt6.QtCore import pyqtSlot, QCoreApplication, QSettings, Qt

from PyQt6.QtWidgets import (QAbstractItemView, QApplication, QDialog,
                             QDialogButtonBox, QFileDialog, QMainWindow, QMenu, QMessageBox,
                             QListWidgetItem)
from PyQt6.QtGui import QStandardItem, QAction, QActionGroup
from PyQt6.QtWebChannel import QWebChannel

from ui import mathmemo_rc  # register Qt resources

from ui_loader import load_ui_class, UI_CLASSES

QCoreApplication.setApplicationName('moltencrux')
QCoreApplication.setOrganizationName('MathMemo')
settings = QSettings()

# Only log debug level messages in debug mode
if __debug__:
    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
    logging.debug('debug mode on')
else:
    logging.basicConfig(stream=sys.stderr, level=logging.ERROR)

Ui_MainWindow = load_ui_class(*UI_CLASSES['MainWindow'])
Ui_settings = load_ui_class(*UI_CLASSES['Settings'])

#from mjrender import (context, mathjax_v2_url, mathjax_url_remote, mathjax_url, mathjax_v2_config,
#                      mathjax_config, page_template)
from mjrender import page_template, mathjax_v3_url


class MainEqWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        # FormulaList.setSettings(self.settings) I don't think this is necessary
        self.initUI()
        self.page_template = page_template
        self.formula_svg = None
        self.eq_queue = []
        self.svg_queue = []
        self.copy_mode = 'image'
        self.default_filename = None

    def initUI(self):
        self.setupUi(self)

        #self.highlight = LatexHighlighter(self.input_box.document())

        # use a separate QWebEngineView for rendering.  Might could be a QWebEnginePage
        # I think I did it like this because I was worried that the page processing was
        # asynchronous and worried if we started to enter a new formula very quickly, that
        # it might interfere with what got inserted into the list.

        #self.input_box.setPlaceholderText("Enter a formula here...")

        # self.input_box.installEventFilter(self)

        # sets proportions for the eq list, preview & input widgets
        #self.splitter.setSizes([500, 350, 150])
        # XXXX  debuging line below
        # self.render.loadFinished.connect(self._on_load_finished)

        # self.input_box.textChanged.connect(self.updatePreview)

        # settings UI
        self.settings_ui = MainSettings()
        self.actionSettings.triggered.connect(self.settings_ui.show)

        # Tool Buttons

        # Copy Profile Menu
        self.copy_menu = QMenu()
        group = QActionGroup(self)
        group.setExclusive(True)

        #XXX experimental

        self.copy_profile_button.setMenu(self.eq_view.build_copy_menu(group))
        ###action.triggered.connect(partial(self.eq_view.setCopyDefault, method))
        group.triggered.connect(self.copy_profile_changed)
        # self.eq_view.itemDoubleClicked.connect(self.editItem)
        ### Experimental

        self.channel = QWebChannel()
        # self.mj_renderer = MathJaxRenderer() using a separate page causes svg rendering to break
        # the QWebEnginePage must be associated with a view
        self.mj_renderer = self.eq_view.mj_renderer
        # self.preview.setPage(self.mj_renderer)
        # self.channel.registerObject('mj_renderer', self.mj_renderer)
        # self.preview.page().setWebChannel(self.channel)
        # self.preview.setHtml(gen_render_html(), QUrl('file://'))

    def editItem(self, item):
        logging.debug('editItem: {}'.format(item))
        self.save_input_state = self.input_box.toPlainText()

    def copy_profile_changed(self, action:QAction):
        logging.debug('copy profile changed {}'.format(action.text()))
        method = action.data()
        logging.debug('method: {}'.format(method))
        self.eq_view.setCopyDefault(method)
        logging.debug('method: {}'.format(self.eq_view.copyDefault))
        logging.debug('method cls: {}'.format(self.eq_view.copyDefault.__func__))

    def show_settings_ui(self):
        response = self.settings_ui.exec()

        if response == QDialogButtonBox.StandardButton.Apply or response == QDialogButtonBox.StandardButton.Ok:
            self.settings_ui.saveSettings()
        if response == QDialogButtonBox.StandardButton.Cancel or response == QDialogButtonBox.StandardButton.Ok:
            self.close()

    def updatePreview(self, ):
        formula_str = self.input_box.toPlainText()
        self.mj_renderer.updatePreview(formula_str)


    def eventFilter(self, obj, event):
        ...

    # def eventFilter(self, obj, event):
    #     if obj is self.input_box and event.type() == QEvent.Type.FocusIn:
    #         # Clear the input box when it receives focus
    #         # self.input_box.setPlainText('')
    #         ...
    #
    #       if event.type() == QEvent.Type.KeyPress and obj is self.input_box:
    #         if event.key() == Qt.Key.Key_Return and self.input_box.hasFocus():
    #             if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
    #                 print('ZZZZZZZZZZZZZcaught ctrl+enter')
    #                 self.commit_current_formula()
    #                 return True  # this seems to delete the trailing \n.. interesting
    #     return False
    #     return super().eventFilter(obj, event)


    def commit_current_formula(self):
        formula_str = self.input_box.toPlainText()

        if formula_str:
            self.eq_view.append_formula(formula_str)
            self.input_box.clear()

    def _on_load_finished(self):
        # Extract the SVG output from the page and add an XML header
        xml_header = b'<?xml version="1.0" encoding="utf-8" standalone="no"?>'
        self.render.runJavaScript("""
            var mjelement = document.getElementById('mathjax-container');
            mjelement.getElementsByTagName('svg')[0].outerHTML;
        """, lambda result: self.update_svg(xml_header + result.encode()))

    def update_svg(self, svg:bytes):
        # add XML header
        formula = self.eq_queue.pop(0)
        self.eq_view.append_formula_svg(formula, svg)

    @pyqtSlot()
    def on_add_new_button_clicked(self):
        # Debounce this: Don't add new when we are editing
        if self.eq_view.state() != QAbstractItemView.State.EditingState:
            self.eq_view.append_new_and_edit()

            # editItem doesn't block, so we don't need to delete anything if user abandons the edit
            # Looks like it needs to be handled in the delegate or editor.


    @pyqtSlot()
    def on_copy_button_clicked(self):
        self.eq_view.copy()

    @pyqtSlot()
    def on_actionAbout_MathMemo_triggered(self):
        # Set up the about window
        about_text = (
            '<html>'
            'A pasteboard for math equations powerd by MathJax.'
            '<div><a href="https://github.com/moltencrux/mathmemo">Visit MathMemo on GitHub</a></div>'
            'Copyright © 2023 A. Graham Cole'
        )
        QMessageBox.about(self, 'About MathMemo', about_text)

    @pyqtSlot()
    def on_actionSave_As_triggered(self):
        filename, filter = QFileDialog.getSaveFileName(self, self.tr('Save F:xile'), '', '')
        if filename:
            self.default_filename = filename
            self.eq_view.save_as_text(filename)

    @pyqtSlot()
    def on_actionSave_triggered(self):
        if self.default_filename:
            self.eq_view.save_as_text(self.default_filename)
        else:
            self.on_actionSave_As_triggered()

    @pyqtSlot()
    def on_actionOpen_triggered(self):
        filename, filter = QFileDialog.getOpenFileName(self, self.tr('Open F:xile'), '', '')
        if filename:
            self.default_filename = filename
            self.eq_view.load_from_text(filename)

    @pyqtSlot()
    def on_actionQuit_triggered(self):
        if self.eq_view.isWindowModified() or True:
            quit_dialog = QMessageBox()
            quit_dialog.setText("You have unsaved formulas.")
            quit_dialog.setInformativeText(
                "Do you want to save before closing? If you don't save, your changes will be lost.")

            quit_dialog.setStandardButtons(
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
            quit_dialog.setDefaultButton(QMessageBox.StandardButton.Save)
            response = quit_dialog.exec()

            if response == QMessageBox.StandardButton.Save:
                self.on_actionSave_triggered()
                app.quit()
            elif response == QMessageBox.StandardButton.Discard:
                app.quit()
'''
        # settings UI
        self.settings_ui = Ui_settings()
        self.settings_dialog = QDialog()
        self.settings_ui.setupUi(self.settings_dialog)
'''
class MainSettings(QDialog, Ui_settings):
    def __init__(self):
        self._settings_changed = False
        super().__init__()

        self.initUI()
        self.setupUi(self)
        self.loadSettings()
        #self.mathjax_ver_comboBox
    def initUI(self):
        ...
    def _settingsChanged(self):
        self._settings_changed = True
    @pyqtSlot()
    def on_rfactor_doubleSpinBox_valueChanged(self):
        self._settingsChanged(self)

    @pyqtSlot()
    def on_buttonBox_accepted(self):
        self.saveSettings()

    @pyqtSlot()
    def on_buttonBox_rejected(self):
        self.loadSettings()

    # settings_hooks = {
    #     "copyImage/reductionFactor":
    #         #copy_img_rfactor_doubleSpinBox.value()
    # }
    @pyqtSlot()
    def on_mathjax_path_pushButton_clicked(self):
        url, filter = QFileDialog.getOpenFileUrl(self, 'Select MathJax Location')
        if url.isValid():
            self.mathjax_path_lineEdit.setText(url.toString())

    def saveSettings(self):
        settings.setValue("copyImage/reductionFactor",
                               self.copy_img_rfactor_doubleSpinBox.value())
        settings.setValue("display/verticalPadding", self.vert_display_img_pad_spinBox.value())

        settings.setValue("display/reductionFactor",
                               self.display_img_rfactor_doubleSpinBox.value())
        settings.setValue("main/mathjaxVersion", self.mathjax_ver_comboBox.currentText())
        settings.setValue("main/mathjaxUrl",
                          self.mathjax_path_lineEdit.text())

        # print('saving: ', self.rfactor_doubleSpinBox.value())
        settings.sync()

    def loadSettings(self):
        self.copy_img_rfactor_doubleSpinBox.setValue(
            settings.value("copyImage/reductionFactor", 12.0, type=float))
        self.vert_display_img_pad_spinBox.setValue(
            settings.value("display/verticalPadding", 200, type=int))
        self.display_img_rfactor_doubleSpinBox.setValue(
            settings.value("display/reductionFactor", 24.0, type=float))
        self.mathjax_ver_comboBox.setCurrentText(
            settings.value("main/mathjaxVersion", '3', type=str))
        self.mathjax_path_lineEdit.setText(
            settings.value("main/mathjaxUrl", mathjax_v3_url, type=str))


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main = MainEqWindow()
    main.show()
    sys.exit(app.exec())
