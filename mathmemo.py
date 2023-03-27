#!/usr/bin/env python3

import sys
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QUrl, QEvent, QSize
from PyQt5.QtGui import QTextDocument, QPalette, QColor
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineSettings
from PyQt5.QtSvg import QSvgWidget, QGraphicsSvgItem
from io import BytesIO
import matplotlib.pyplot as plt

from PyQt5.QtWidgets import (QWidget, QSlider, QLineEdit, QLabel, QPushButton, QScrollArea,QApplication,
                             QHBoxLayout, QVBoxLayout, QMainWindow, QSizePolicy)

from PyQt5 import QtWidgets, uic

# from PyQt5 import Qt
# 'PyQt5.QtWebEngineWidgets.QWebEngineSettings.ShowScrollBars'


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
        }
      });
""".replace('{', '{{').replace('}', '}}')

mathjax_config = """
window.MathJax = {
    options: {
        enableMenu: false, ignoreHtmlClass:
            'tex2jax_ignore', processHtmlClass:
            'tex2jax_process' },
    tex: { packages: ['base', 'ams', 'noerrors', 'noundefined'] },
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
    <div>
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

class EquationBox(QWidget):
    def __init__(self, parent=None, formulas=[]):
        super().__init__(parent)
        self.setLayout(QVBoxLayout())
        self.layout().setSpacing(10)
        self.layout().addStretch(1)
        #frame = QFrame()
        self.views = []
        self.formulas = []
        self.page_template = page_template
        for formula in formulas:
            self.append_formula(formula)
            
        # self.setAutoFillBackground(True);
        ######
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet('background-color: white;')
        # pal = self.palette()
        # pal.setColor(self.backgroundRole(), Qt.white)
        # self.setPalette(pal)




    def append_formula_svg_mpl(self, formula):
        self.formulas.append(formula)
        svg = QSvgWidget()
        svg_data = render_latex_as_svg(formula)
        svg.load(svg_data)
        svg.renderer().setAspectRatioMode(Qt.KeepAspectRatio)
        # svg.sizeHint() returns (460, 345)
        self.layout().addWidget(svg)
        self.views.append(svg)

    def append_formula_svg(self, formula, svg:bytes):

        # QGraphicsSvgItem()
        self.formulas.append(formula)
        svg_widget = QSvgWidget()
        svg_widget.load(svg)
        svg_widget.renderer().setAspectRatioMode(Qt.KeepAspectRatio)
        print("sfh: ", svg_widget.renderer().defaultSize().height() // 2)
        svg_widget.setFixedHeight( svg_widget.renderer().defaultSize().height() // 24)
        policy = QSizePolicy()
        # policy.setWidthForHeight(True)
        # policy.setHorizontalPolicy(QSizePolicy.)
        policy.setVerticalPolicy(QSizePolicy.Fixed)
        # svg_widget.setSizePolicy(policy)
        # pal = QPalette(svg_widget.palette())
        # pal.setColor(QPalette.Window, QColor('red'))
        # svg_widget.setPalette(pal)
        svg_widget.setAutoFillBackground(True)
        print('svg sizeHint: ', svg_widget.sizeHint())

        # svg.sizeHint() returns (460, 345)
        print('svg_widegt size hint: ', svg_widget.sizeHint())
        self.layout().addWidget(svg_widget)
        self.views.append(svg_widget)

    def append_formula(self, formula):
        self.formulas.append(formula)
        view = QWebEngineView()
        view.setFixedHeight(200)
        # view.setAttribute(QWebEngineSettings.ShowScrollBars)
        view.settings().setAttribute(QWebEngineSettings.ShowScrollBars, False)
        # view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setHtml(self.page_template.format(formula=formula), QUrl('file://'))
        self.views.append(view)
        self.layout().addWidget(view)
        print(view.page().toHtml(QString()))

    def append_label(self, label):
        object = QLabel("TextLabel: " + label)
        self.layout().addWidget(object)


class MainEqWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.page_template = page_template
        self.formula_svg = None
        self.eq_queue = []
        self.svg_queue = []

    def initUI(self):

        self.widget = QSplitter(Qt.Vertical)

        # sp = QSizePolicy()
        # sp.setVerticalStretch(255)
        # self.widget.setSizePolicy(sp)

        self.widget.setLayout(QVBoxLayout())

        self.input_box = QPlainTextEdit()
        self.preview = QWebEngineView()
        self.render = QWebEngineView()

        self.preview.setFixedHeight(200)
        # self.preview.setAttribute(QWebEngineSettings.ShowScrollBars)
        self.preview.settings().setAttribute(QWebEngineSettings.ShowScrollBars, False)
        # self.preview.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.input_box.setPlaceholderText("Enter a formula here...")
        self.input_box.installEventFilter(self)
        # sp = QSizePolicy()
        # sp.setVerticalStretch(0)
        # self.input_box.setSizePolicy(sp)

        self.scroll = QScrollArea()


        self.scroll.setWidgetResizable(True) # CRITICAL

        self.eq_box= EquationBox()
        self.scroll.setWidget(self.eq_box)  # CRITICAL

        self.widget.layout().addWidget(self.scroll)
        self.widget.layout().addWidget(self.preview)
        self.widget.layout().addWidget(self.input_box)
        self.setCentralWidget(self.widget)
        # self.input_box.installEventFilter(self)
        #self.show()
        # self.preview.page().loadFinished.connect(self._on_load_finished)
        print('connecting')
        self.render.loadFinished.connect(self._on_load_finished)

        self.input_box.textChanged.connect(self.updatePreview)

    def append_content(self, content):
        # Append the message to the conversation
        content_html= f"{content}<br>"
        if '\\(' in content and '\\)' in content:
            # Use MathJax to render math expressions enclosed in \( and \)
            content_html = content_html.replace('\\(', '<mathjax style="font-size:2.3em" >').replace('\\)', '</mathjax>')
        # js_code = f"document.body.innerHTML += '{content_html}'; MathJax.typeset();"
        # self.text_area.page().runJavaScript(js_code)
        self.eq_box.append_formula(content)
        # self.formula.append_label(content)
        # self.formula.append_formula_old(content)
        # Scroll to the bottom of the conversation
        # self.text_area.page().runJavaScript("window.scrollTo(0, document.body.scrollHeight);")
        # self.scroll.verticalScrollBar().setValue() #setAlignment(Qt.AlignBottom)
        # const scrollArea = this.$refs.chatScroll;
        # const scrollTarget = scrollArea.getScrollTarget();
        # const duration = 300; // ms - use 0 to instant scroll
        # scrollArea.setScrollPosition(scrollTarget.scrollHeight, duration);

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
                    # event.accept() # not sure what this was doing.  it didn't solve the \n issue
                    print('Shift+Enter pressed')
                    formula_str = self.input_box.toPlainText()


                    # view.setFixedHeight(200)
                    # view.setAttribute(QWebEngineSettings.ShowScrollBars)
                    # view.settings().setAttribute(QWebEngineSettings.ShowScrollBars, False)
                    # view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

                    if formula_str:
                        print('appending formula: ', formula_str)
                        self.eq_queue.append(formula_str)
                        print('svg: ', self.formula_svg)
                        self.input_box.clear()

                    print('template: ', self.page_template.format(formula=formula_str))
                    self.render.setHtml(self.page_template.format(formula=formula_str),
                                         QUrl('file://'))
                    return True # this seems to delete the trailing \n.. interesting

        return super().eventFilter(obj, event)

    def queue_result(result):
        ...

    def _on_load_finished(self):
        # Extract the SVG output from the page
        print('on load finished')
        #self.preview.page().runJavaScript("""
        #    document.getElementsByTagName('svg')[0].outerHTML;
        #""", lambda result: setattr(self, 'formula_svg', result))
        self.render.page().runJavaScript("""
            var mjelement = document.getElementById('mathjax-container');
            mjelement.getElementsByTagName('svg')[0].outerHTML;
        """, lambda result: self.update_svg(result.encode()))
        print('olf svg: ', self.formula_svg)

    def update_svg(self, svg):
        # self.svg_queue.append(svg)
        formula = self.eq_queue.pop(0)
        print('update_svg svg: ', svg)
        print('svg type: ', type(svg))
        print('update_svg formula: ', formula)
        self.eq_box.append_formula_svg(formula, svg)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main = MainEqWindow()
    main.show()
    sys.exit(app.exec_())
