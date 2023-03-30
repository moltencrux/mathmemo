#!/usr/bin/env python3

import sys
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QUrl, QEvent, QSize, QItemSelection, QItemSelectionModel, QMimeData
from PyQt5.QtGui import QTextDocument, QPalette, QColor, QCursor, QClipboard, QImage, QPainter
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineSettings
from PyQt5.QtSvg import QSvgWidget, QGraphicsSvgItem, QSvgRenderer
from io import BytesIO
import matplotlib.pyplot as plt

from PyQt5.QtWidgets import (QWidget, QSlider, QLineEdit, QLabel, QPushButton, QScrollArea,QApplication,
                             QHBoxLayout, QVBoxLayout, QMainWindow, QSizePolicy, QAbstractItemView)

from PyQt5 import QtWidgets, uic

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

class FormulaList(QListWidget):
    SvgRole = Qt.UserRole
    FormulaRole = Qt.UserRole + 1

    def __init__(self, parent=None, formulas=[]):
        super().__init__(parent)
        #self.itemSelectionChanged.connect()
        #self.selectionChanged.connect
        # self.setSizeAdjustPolicy(QListWidget.SizeAdjustPolicy.AdjustToContents)
        self.currentItemChanged.connect(lambda: print("QLW: Item Changed Signal"))
        self.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.setUniformItemSizes(False)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        # self.setStyleSheet("QListWidget:item { selection-background-color: red; }")
        # self.setStyleSheet("QListWidget::item:selected { background-color: red; }")
        self.setSpacing(1)

        # self.setLayout(QVBoxLayout())
        # self.layout().setSpacing(10)
        # self.layout().addStretch(1)
        #frame = QFrame()
        self.setViewMode(QListWidget.ListMode)
        self.views = []
        self.formulas = []
        self.images = []
        self.page_template = page_template
        for formula in formulas:
            self.append_formula(formula)

        # self.setAutoFillBackground(True);
        ######
        #self.setAttribute(Qt.WA_StyledBackground, True)
        # self.setStyleSheet('background-color: white;')
        #self.setStyleSheet("QListWidget::item:selected { background-color: red; }")
        #self.setStyleSheet("QListWidget { background-color: white; }")
        #self.setStyleSheet('QListView::item:selected { border : 2px solid red; background : green; }')
        """ diabling temporarily 
        self.setStyleSheet("QListWidget"
                                  "{"
                                  "background : white;"
                                  "}"
                                  "QListWidget QScrollBar"
                                  "{"
                                  "background : lightblue;"
                                  "}"
                                  "QListView::item:selected"
                                  "{"
                                  "border : 8px solid red;"
                                  "background : green;"
                                  "}"
                                  )
       """

        # pal = self.palette()
        # pal.setColor(self.backgroundRole(), Qt.white)
        # self.setPalette(pal)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.listContextMenuReuquested)
        self.itemSelectionChanged.connect(self.itemChanged)

    def itemChanged(self):

        for item in [self.item(i) for i in range(self.count())]:
            svg_widget = self.itemWidget(item)
            if item.isSelected():
                #item.setBackgroundColor(Qt.green)
                #svg_widget.setStyleSheet("QSvgWidget { background: cyan; }")
                #svg_widget.setAutoFillBackground(True)
                #pal = QPalette(svg_widget.palette())
                # svg_widget.palette().Background.setColor(QColor('cyan'))
                #pal.setColor(QPalette.Background, QColor('cyan'))
                # svg_widget.setPalette(pal)
                # pal = QPalette()
                svg_widget.setBackgroundRole(QPalette.Highlight)
                svg_widget.setForegroundRole(QPalette.HighlightedText)

            else:
                # svg_widget.setStyleSheet("QSvgWidget { background: white; }")
                svg_widget.setForegroundRole(QPalette.BrightText)
                svg_widget.setBackgroundRole(QPalette.Base)

        # order: [group]role
        #c = pal.color(QPalette.Window, QPalette.Highlight)
        # c = pal.color(QPalette.Highlight)
        # print('color: ', c)
        # print('color: ', QPalette.Highlight)
        print('type h: ', type(QPalette.Highlight))
        print('type w: ', type(QPalette.WindowText))
        #print('type: ', type(QPalette.Highlight))
        # QPalette.Highlight
        # QPalette.HighlightedText
        #pal = QPalette(svg_widget.palette())
        #pal.setColor(QPalette.Window, QColor('red'))
        #svg_widget.setPalette(pal)
        #svg_widget.setAutoFillBackground(True)

    def listContextMenuReuquested(self, pos):
        print('context menu requested')

        pos = self.mapFromGlobal(QCursor.pos())
        row = self.indexAt(pos).row()

        self.cmenu = QMenu(self)
        menu = self.cmenu
        copy_svg_act = menu.addAction('Copy SVG')
        copy_img_act = menu.addAction('Copy Image')
        copy_eq_act = menu.addAction('Copy Equation')
        menu.addSeparator()
        delete_act = menu.addAction('Delete')

        if row < 0:
            for action in [copy_svg_act, copy_img_act, copy_eq_act, delete_act]:
                action.setDisabled(True)


        action = menu.exec_(self.mapToGlobal(pos))
        if action == copy_svg_act:
            self.copySvg(row)
        elif action == copy_img_act:
            self.copyImage(row)
        elif action == copy_eq_act:
            self.copyEquation(row)
        elif action == delete_act:
            self.deleteEquation(row)

        print("Context action {} performed on: {}".format(action, row))


    def copySvg(self, index):
        print('copySVG called ', index)

        item = self.item(index)
        svg = item.data(self.SvgRole)

        svg_widget = self.itemWidget(item)

        # create a QSvgRenderer and set it to the QSvgWidget
        svg_renderer = svg_widget.renderer()
        # svg_widget.setSharedRenderer(svg_renderer)

        # create a QMimeData object and set the SVG data
        mime_data = QMimeData()
        print("copySVG: image type: ", type(self.images[index]))
        # mime_data.setData("image/svg+xml", self.images[index])
        mime_data.setData("image/svg", svg.replace(b'currentColor', b'red')) # works for Anki
        ##  data:image/svg+xml ???

        # mime_data.setData("image/svg+xml", self.images[index].replace(b'currentColor', b'red'))
        # mime_data.setData("image/svg+xml"
        # mime_data.setData("image/svg"

        # get the system clipboard and set the QMimeData object
        clipboard = app.clipboard()
        clipboard.setMimeData(mime_data)
        # print('clipboard data: ', clipboard.mimeData().data())
        if clipboard.mimeData().hasImage():
            print('has image')


    def copyImage(self, index):
        # FIX: Try scaling down the image size to see if Anki likes that
        # more.  Mozilla seems to be fine with it tho

        item = self.item(index)
        svg = item.data(self.SvgRole)
        renderer = QSvgRenderer()
        renderer.load(svg.replace(b'currentColor', b'white'))

        # Render the SVG into a QImage
        image = QImage(renderer.defaultSize() * 0.2, QImage.Format_RGB666)

        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        app.clipboard().setImage(image)
        print('copyImage called ', index)

    def copyEquation(self, index):

        item = self.item(index)
        formula = item.data(self.FormulaRole)

        app.clipboard().setText(self.formulas[index])
        #app.clipboard().setText(formula) # this worked

        print('all', self.formulas)
        print('copyEquation called ', self.formulas[index])

    def deleteEquation(self, index):
        self.formulas.pop(index)
        self.images.pop(index)
        self.takeItem(index)


        print('deleteEquation called ', index)

    #def contextMenuEvent(self, a0: QtGui.QContextMenuEvent) -> None:
    #    ...

    def append_formula_svg_matplotlib(self, formula):
        self.formulas.append(formula)
        svg = QSvgWidget()
        svg_data = render_latex_as_svg(formula)
        svg.load(svg_data)
        svg.renderer().setAspectRatioMode(Qt.KeepAspectRatio)
        # svg.sizeHint() returns (460, 345)
        self.layout().addWidget(svg)
        self.views.append(svg)

    def append_formula_svg(self, formula, svg:bytes):

        item = QListWidgetItem()
        item.setData(self.FormulaRole, formula)
        item.setData(self.SvgRole, svg)

        self.formulas.append(formula)
        self.images.append(svg)
        svg_widget = QSvgWidget()

        # This can replace the color in the svg data
        # svg = svg.replace(b'currentColor', b'red')

        svg_widget.load(svg)
        svg_widget.renderer().setAspectRatioMode(Qt.KeepAspectRatio)
        svg_widget.renderer().setViewBox(svg_widget.renderer().viewBox().adjusted(0, -200, 0, 200))
        svg_widget.setFixedHeight( svg_widget.renderer().defaultSize().height() // 24)

        # effectively adds padding around the QSvgWidget
        print("view box: ", svg_widget.renderer().viewBox())

        print("sfh resized: ", svg_widget.renderer().defaultSize().height())
        policy = QSizePolicy()
        # policy.setWidthForHeight(True)
        # policy.setHorizontalPolicy(QSizePolicy.)
        policy.setVerticalPolicy(QSizePolicy.Fixed)
        # svg_widget.setSizePolicy(policy)

        # this works, but disabling temporarily, might be overriding sth
        #self.setStyleSheet("QSvgWidget { background: white; }")


        print('svg sizeHint: ', svg_widget.sizeHint())

        print('svg_widegt size hint: ', svg_widget.sizeHint())
        # item.setContentsMargins(0, 5, 0, 5)  #no effect?
        item.setSizeHint(QSize(0, svg_widget.renderer().defaultSize().height() // 24))
        #self.setStyleSheet("QListWidgetItem:item { selection-background-color: blue; }")
        #self.setStyleSheet("QListView::item:selected { background-color: blue; }")

        self.addItem(item)
        self.setItemWidget(item, svg_widget)

        self.views.append(item)
        self.scrollToBottom()

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

        #self.preview.setFixedHeight(200)
        # self.preview.setAttribute(QWebEngineSettings.ShowScrollBars)
        self.preview.settings().setAttribute(QWebEngineSettings.ShowScrollBars, False)
        # self.preview.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.input_box.setPlaceholderText("Enter a formula here...")
        self.input_box.installEventFilter(self)
        # sp = QSizePolicy()
        # sp.setVerticalStretch(0)
        # self.input_box.setSizePolicy(sp)

        self.eq_box= FormulaList()

        self.widget.layout().addStretch(1)
        self.widget.layout().addWidget(self.eq_box)
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
                    # print('Shift+Enter pressed')
                    formula_str = self.input_box.toPlainText()

                    if formula_str:
                        print('appending formula: ', formula_str)
                        self.eq_queue.append(formula_str)
                        print('svg: ', self.formula_svg)
                        self.input_box.clear()

                    self.render.setHtml(self.page_template.format(formula=formula_str),
                                         QUrl('file://'))
                    return True # this seems to delete the trailing \n.. interesting

        return super().eventFilter(obj, event)


    def _on_load_finished(self):
        # Extract the SVG output from the page and add an XML header
        xml_header = b'<?xml version="1.0" encoding="utf-8" standalone="no"?>'
        self.render.page().runJavaScript("""
            var mjelement = document.getElementById('mathjax-container');
            mjelement.getElementsByTagName('svg')[0].outerHTML;
        """, lambda result: self.update_svg(xml_header + result.encode()))
        print('olf svg: ', self.formula_svg)

    def update_svg(self, svg:bytes):
        # add XML header
        formula = self.eq_queue.pop(0)
        self.eq_box.append_formula_svg(formula, svg)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main = MainEqWindow()
    main.show()
    sys.exit(app.exec_())
