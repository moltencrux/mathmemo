#!/usr/bin/env python3

import sys
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QUrl, QEvent, QSize, QItemSelection, QItemSelectionModel, QMimeData, pyqtSlot
from PyQt5.QtGui import QTextDocument, QPalette, QColor, QCursor, QClipboard, QImage, QPainter
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineSettings
from PyQt5.QtSvg import QSvgWidget, QGraphicsSvgItem, QSvgRenderer
from io import BytesIO
from texsyntax import LatexHighlighter
import matplotlib.pyplot as plt

from PyQt5.QtWidgets import (QWidget, QSlider, QLineEdit, QLabel, QPushButton, QScrollArea,QApplication,
                             QHBoxLayout, QVBoxLayout, QMainWindow, QSizePolicy, QAbstractItemView)

from PyQt5 import QtWidgets, uic

from formulalist import FormulaList
from mainwindow_ui import Ui_MainWindow
from settings_ui import Ui_settings

from pysvg.parser import parse

# from PyQt5 import Qt
# 'PyQt5.QtWebEngineWidgets.QWebEngineSettings.ShowScrollBars'
'''
void setHeight (QPlainTextEdit *ptxt, int nRows)
{
    QTextDocument *pdoc = ptxt->document ();
    QFontMetrics fm (pdoc->defaultFont ());
    QMargins margins = ptxt->contentsMargins ();
    int nHeight = fm.lineSpacing () * nRows +
        (pdoc->documentMargin () + ptxt->frameWidth ()) * 2 +
        margins.top () + margins.bottom ();
    ptxt->setFixedHeight (nHeight);
}
'''

mathjax_code = r'\frac{{d}}{{dx}} (x^2) = 2x'

context = r'''\newcommand{\Ex}{\mathop{\rm Ex}}
               \newcommand{\T}{\mathop{\rm T}}
               \newcommand{\range}{\mathop{\rm range}}
           '''.replace('{', '{{').replace('}', '}}')


mathjax_v2_url = "file:///usr/share/javascript/mathjax/MathJax.js?delayStartupUntil=onload"
# mathjax_url = "file:///usr/share/anki/web/mathjax/MathJax.js"

mathjax_url_remote = "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js?delayStartupUntil=onload"

mathjax_url = 'file:///usr/share/javascript/mathjax@3/es5/tex-svg-full.js'

# Then, write a multi-line string containing HTML code. The code should import the MathJax javascript module. Then,
# write your mathematical equation...


mathjax_config_old = """
      MathJax.Hub.Config({
        showMathMenu: false,
        jax: ['input/TeX', 'output/SVG'],
        extensions: ['tex2jax.js', 'MathMenu.js', 'MathZoom.js'],
        TeX: {
          extensions: ['AMSmath.js', 'AMSsymbols.js', 'noErrors.js', 'noUndefined.js']
        }
      });
""".replace('{', '{{').replace('}', '}}')

mathjax_v2_config = """
      MathJax.Hub.Config({
        jax: ["input/TeX","input/MathML","input/AsciiMath","output/SVG"],
        extensions: ["tex2jax.js","mml2jax.js","asciimath2jax.js","MathMenu.js",
                     "MathZoom.js","AssistiveMML.js", "a11y/accessibility-menu.js"],
        TeX: { extensions:
          ["AMSmath.js","AMSsymbols.js","noErrors.js","noUndefined.js"]
      });
""".replace('{', '{{').replace('}', '}}')

mathjax_config = """
window.MathJax = {
    options: {
        enableMenu: false, ignoreHtmlClass:
            'tex2jax_ignore', processHtmlClass:
            'tex2jax_process' },
    tex: { packages: ['base', 'ams', 'noerrors', 'noundefined', '+', 'color']
           color: { padding: 5px
                    borderWidth: 5px
           }
    },
    loader: { load: ['input/tex-base', 'output/svg', 'ui/menu',
                      '[tex]/require'] },
};
""".replace('{', '{{').replace('}', '}}')

page_template = """
<html>
  <head>
    <script type="text/javascript" id="MathJax-script"
      src="{url}">
    </script>
    <script type="text/x-mathjax-config">
        {config}
    </script>
  </head>
  <body>
    <div style="background-color: white">
      <mathjax id="mathjax-context" style="font-size:2.3em">$${context}$$</mathjax>
      <mathjax id="mathjax-container" style="font-size:2.3em">$${{formula}}$$</mathjax>
    </div>
  </body>
</html>
""".format(url=mathjax_url, context=context, config=mathjax_config)

plt.rc('mathtext', fontset='cm')

def render_latex_as_svg(latex_formula):
    fig, ax = plt.subplots()
    ax.text(0.5, 0.5, fr'${latex_formula}$', size=30, ha='center', va='center')
    # ax.text(0.5, 0.5, fr'[{latex_formula}]', size=30, ha='center', va='center')
    ax.set_axis_off()
    buffer = BytesIO()
    plt.savefig(buffer, format='svg')
    svg_image = buffer.getvalue()
    buffer.close()
    plt.close(fig)
    return svg_image

class MainEqWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.page_template = page_template
        self.formula_svg = None
        self.eq_queue = []
        self.svg_queue = []

    def initUI(self):
        self.setupUi(self)

        self.highlight = LatexHighlighter(self.input_box.document())

        # use a separate QWebEngineView for rendering.  Might could be a QWebEnginePage
        # I think I did it like this because I was worried that the page processing was
        # asynchronous and worried if we started to enter a new formula very quickly, that
        # it might interfere with what got inserted into the list.

        self.render = QWebEnginePage()

        #self.input_box.setPlaceholderText("Enter a formula here...")

        self.input_box.installEventFilter(self)

        # sets proportions for the eq list, preview & input widgets
        self.splitter.setSizes([500, 350, 150])
        # self.preview.page().loadFinished.connect(self._on_load_finished)
        print('connecting')
        # self.render.loadFinished.connect(self._on_load_finished)
        self.render.loadFinished.connect(self._on_load_finished)

        self.input_box.textChanged.connect(self.updatePreview)

        # settings UI
        self.settings_ui = Ui_settings()
        self.settings_dialog = QDialog()
        self.settings_ui.setupUi(self.settings_dialog)
        self.actionSettings.triggered.connect(self.settings_dialog.show)

    def append_content(self, content):
        # Append the formula to the list box
        content_html= f"{content}<br>"
        if '\\(' in content and '\\)' in content:
            # Use MathJax to render math expressions enclosed in \( and \)
            content_html = content_html.replace('\\(', '<mathjax style="font-size:2.3em" >').replace('\\)', '</mathjax>')
        # js_code = f"document.body.innerHTML += '{content_html}'; MathJax.typeset();"
        # self.text_area.page().runJavaScript(js_code)
        self.eq_box.append_formula(content)

    def updatePreview(self):
        formula_str = self.input_box.toPlainText()
        self.preview.setHtml(self.page_template.format(formula=formula_str), QUrl('file://'))

    def eventFilter(self, obj, event):
        if obj is self.input_box and event.type() == QEvent.FocusIn:
            # Clear the input box when it receives focus
            # self.input_box.setPlainText('')
            ...

        if event.type() == QEvent.KeyPress and obj is self.input_box:
            if event.key() == Qt.Key_Return and self.input_box.hasFocus():
                if event.modifiers() & Qt.ControlModifier:
                    self.add_current_formula()
                    return True # this seems to delete the trailing \n.. interesting

        return super().eventFilter(obj, event)

    def add_current_formula(self):
        formula_str = self.input_box.toPlainText()

        if formula_str:
            print('appending formula: ', formula_str)
            self.eq_queue.append(formula_str)
            print('svg: ', self.formula_svg)
            self.input_box.clear()

        self.render.setHtml(self.page_template.format(formula=formula_str),
                            QUrl('file://'))

    def _on_load_finished(self):
        # Extract the SVG output from the page and add an XML header
        xml_header = b'<?xml version="1.0" encoding="utf-8" standalone="no"?>'
        self.render.runJavaScript("""
            var mjelement = document.getElementById('mathjax-container');
            mjelement.getElementsByTagName('svg')[0].outerHTML;
        """, lambda result: self.update_svg(xml_header + result.encode()))
        print('olf svg: ', self.formula_svg)

    def update_svg(self, svg:bytes):
        # add XML header
        formula = self.eq_queue.pop(0)
        self.eq_box.append_formula_svg(formula, svg)

    @pyqtSlot()
    def on_add_formula_button_clicked(self):
        self.add_current_formula()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    main = MainEqWindow()
    main.show()
    sys.exit(app.exec_())
