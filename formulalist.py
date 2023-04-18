import logging, sys, os
from functools import partial
from enum import Enum, StrEnum
from PyQt5.QtWidgets import (qApp, QAction, QActionGroup, QListWidget, QLabel, QSizePolicy,
                             QAbstractItemView, QListWidgetItem, QMenu)
from PyQt5.QtCore import (pyqtSignal, QDir, Qt, QMimeData, QMutex, QMutexLocker, QSettings, QSize,
                          QTemporaryFile, QUrl)
from PyQt5.QtGui import QPalette, QCursor, QImage, QPainter, QPixmap
from PyQt5.QtSvg import QSvgWidget, QSvgRenderer
from PyQt5.QtWebEngineWidgets import QWebEnginePage
from mjrender import (context, mathjax_v2_url, mathjax_url_remote, mathjax_url, mathjax_v2_config,
                      mathjax_config, page_template)

from menubuilder import build_menu, disable_unused_submenus

from io import BytesIO

class CopyProfile(StrEnum):
    SVG = 'SVG'
    SVG_TEXT = 'SVG Text'
    IMG = 'Image'
    IMG_TMP = 'Temporary Image File'
    EQ = 'Latex Equation'




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
    settings = QSettings()
    copyDefault = lambda: None
    item_ops = set()
    register = partial(lambda s, e: (s.add(e) or e), item_ops)



    def __init__(self, parent=None, formulas=[]):
        super().__init__(parent)
        self.tempfiles = []
        self.formula_queue = []
        self.init_action_dicts()
        self.formula_queue_mutex= QMutex()
        self.clipboard = qApp.clipboard()

        self.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.setUniformItemSizes(False)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setSpacing(1)

        self.setViewMode(QListWidget.ListMode)
        self.formula_page = QWebEnginePage()
        self.formula_page.loadFinished.connect(self._on_load_finished)

        for formula in formulas:
            self.append_formula(formula)
        self.setStyleSheet("QListWidget"
                                  "{"
                                  "background : white;"
                                  "}"
                                  "QListView::item:selected"
                                  "{"
                                  "border : 2px solid blue;"
                                  "background : lightblue;"
                                  "}"
                                  )

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.listContextMenuRequested)
        self.itemSelectionChanged.connect(self.itemChanged)
        self.copyDefault = self.copyEquation

    @classmethod
    def setSettings(cls, settings:QSettings):
        # maybe totally unecessary
        cls.settings = settings

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

                #svg_widget.setBackgroundRole(QPalette.Highlight)
                #svg_widget.setForegroundRole(QPalette.HighlightedText)
                ...

            else:
                # svg_widget.setStyleSheet("QSvgWidget { background: white; }")
                #svg_widget.setForegroundRole(QPalette.BrightText)
                #svg_widget.setBackgroundRole(QPalette.Base)
                ...

        # order: [group]role
        #c = pal.color(QPalette.Window, QPalette.Highlight)
        # c = pal.color(QPalette.Highlight)
        # print('color: ', c)
        # print('color: ', QPalette.Highlight)
        logging.debug('type h: {}'.format(type(QPalette.Highlight)))
        logging.debug('type w: {}'.format(type(QPalette.WindowText)))
        #print('type: ', type(QPalette.Highlight))
        # QPalette.Highlight
        # QPalette.HighlightedText
        #pal = QPalette(svg_widget.palette())
        #pal.setColor(QPalette.Window, QColor('red'))
        #svg_widget.setPalette(pal)
        #svg_widget.setAutoFillBackground(True)

    def listContextMenuRequested(self, pos):
        print('context menu requested')
        pos = self.mapFromGlobal(QCursor.pos())
        row = self.indexAt(pos).row()

        if row < 0 and not self.selectedItems():
            index_items_enabled = False
        else:
            index_items_enabled = True

        menu = build_menu(self.copy_menu_struct, enabled=index_items_enabled)
        first = menu.actions()
        first = first[0] if first else None
        menu.insertSection(first, 'Copy by Method:')
        menu.addSeparator()
        delete_act = menu.addAction('Delete')
        delete_act.setEnabled(index_items_enabled)
        delete_act.setData(self.deleteEquation.__func__)

        selection = menu.exec_(self.mapToGlobal(pos))
        logging.debug("CM selection: {} row {}".format(selection, row))

        if selection:
            command = selection.data()
            if command:
                if row < 0:
                    try:
                       row = self.selectedIndexes()[0].row()
                    except (AttributeError, IndexError):
                       pass

                if row >= 0:
                    logging.debug(f'data is {command}')
                    command(self, row)

        logging.debug("Context action {} performed on: {}".format(selection, row))

    def listContextMenuRequested_old(self, pos):
        print('context menu requested')

        pos = self.mapFromGlobal(QCursor.pos())
        row = self.indexAt(pos).row()

        self.cmenu = QMenu(self)
        menu = self.cmenu
        act = menu.addSection('Copy by Method:')

        copy_svg_act = menu.addAction('Copy SVG')
        copy_svg_text_act = menu.addAction('Copy SVG Text')
        copy_img_act = menu.addAction('Copy Image')
        copy_img_tmp_act = menu.addAction('Copy Image from temporary file')
        copy_eq_act = menu.addAction('Copy Equation')
        menu.addSeparator()
        delete_act = menu.addAction('Delete')

        if row < 0:
            for action in [copy_svg_act, copy_svg_text_act, copy_img_act, copy_img_tmp_act,
                           copy_eq_act, delete_act]:
                action.setDisabled(True)


        action = menu.exec_(self.mapToGlobal(pos))
        if action == copy_svg_act:
            self.copySvg(row)
        elif action == copy_svg_text_act:
            self.copySvgText(row)
        elif action == copy_img_act:
            self.copyImage(row)
        elif action == copy_img_tmp_act:
            self.copyImageTmp(row)
        elif action == copy_eq_act:
            self.copyEquation(row)
        elif action == delete_act:
            self.deleteEquation(row)

        print("Context action {} performed on: {}".format(action, row))


    @register
    def copySvg(self, index):

        item = self.item(index)
        svg = item.data(self.SvgRole)

        # create a QMimeData object and set the SVG data
        mime_data = QMimeData()
        print("copySVG: image type: ", type(self.itemWidget(item)))
        # mime_data.setData("image/svg+xml", self.images[index])
        mime_data.setData("image/svg", svg.replace(b'currentColor', b'red')) # works for Anki

        # mime_data.setData("image/svg+xml", self.images[index].replace(b'currentColor', b'red'))
        # mime_data.setData("image/svg+xml"
        # mime_data.setData("image/svg"

        # get the system clipboard and set the QMimeData object
        self.clipboard.setMimeData(mime_data)

        if self.clipboard.mimeData().hasImage():
            print('has image')

    @register
    def copySvgText(self, index):

        item = self.item(index)
        svg = item.data(self.SvgRole)
        qApp.clipboard().setText(svg.decode())


    @register
    def copyImage(self, index):

        image = self.genPngByIndex(index)
        self.clipboard.setImage(image)
        logging.debug(f'copyImage called {index}')

    def genPngByIndex(self, index):

        rfactor = self.settings.value("copyImage/reductionFactor", 12.0)
        # eventually i want to make this a more intutive setting, something related to
        # dpi  # i think a ratio of 12 may be very close to 600dpi
        # so then a ratio of 6 would be 1200 dpi, 24 would be 300, 48: 150

        item = self.item(index)
        svg = item.data(self.SvgRole)

        renderer = QSvgRenderer()
        renderer.load(svg.replace(b'currentColor', b'black'))
        image = QImage(renderer.defaultSize() / rfactor, QImage.Format_ARGB32)
        #image = QImage(renderer.defaultSize() / rfactor, QImage.Format_RGB666)
        #image.fill(0x00000000)  # fill the image with transparent pixels
        image.fill(Qt.white)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        return image

    @register
    def copyImageTmp(self, index):
        image = self.genPngByIndex(index)

        tmp_imgfile = QTemporaryFile(os.path.join(QDir.tempPath(), 'XXXXXXXX.png'))
        self.tempfiles.append(tmp_imgfile)
        image.save(tmp_imgfile)
        filename = tmp_imgfile.fileName()
        logging.debug('tmp filename: {}'.format(filename))
        tmp_imgfile.close()
        logging.debug('closed')
        data = QMimeData()
        url = QUrl.fromLocalFile(filename)
        data.setUrls([url])
        qApp.clipboard().setMimeData(data)


    @register
    def copyEquation(self, index):

        item = self.item(index)
        formula = item.data(self.FormulaRole)

        qApp.clipboard().setText(formula)

        logging.debug(f'copyEquation called {formula}')

    def copy(self):
        try:
            row = self.selectedIndexes()[0].row()
        except (IndexError, AttributeError):
            row = -1
        else:
            if row >= 0:
                self.copyDefault(row)

    def setCopyDefault(self, mode):

        copyMethod = {'svg': self.copyDefault,
                      'svgtext': self.copySvgText,
                      'formula': self.copyEquation,
                      'image': self.copyImage,
                      'imagetmp': self.copyImageTmp}.get(mode, lambda index: None)

        self.copyDefault = copyMethod

    @register
    def deleteEquation(self, index):
        # self.formulas.pop(index)
        # self.images.pop(index)
        self.takeItem(index)

    def append_formula_svg_matplotlib(self, formula):
        # self.formulas.append(formula)
        svg = QSvgWidget()
        svg_data = render_latex_as_svg(formula)
        svg.load(svg_data)
        svg.renderer().setAspectRatioMode(Qt.KeepAspectRatio)
        # svg.sizeHint() returns (460, 345)
        self.layout().addWidget(svg)

    def append_formula_svg(self, formula, svg:bytes):

        item = QListWidgetItem()
        item.setData(self.FormulaRole, formula)
        item.setData(self.SvgRole, svg)

        # self.formulas.append(formula)
        # self.images.append(svg)
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
        policy.setVerticalPolicy(QSizePolicy.Fixed)

        print('svg sizeHint: ', svg_widget.sizeHint())

        print('svg_widegt size hint: ', svg_widget.sizeHint())
        # item.setContentsMargins(0, 5, 0, 5)  #no effect?
        item.setSizeHint(QSize(0, svg_widget.renderer().defaultSize().height() // 24))

        self.addItem(item)
        self.setItemWidget(item, svg_widget)

        self.scrollToBottom()


    def _on_load_finished(self):
        # Extract the SVG output from the page and add an XML header
        xml_header = b'<?xml version="1.0" encoding="utf-8" standalone="no"?>'
        self.formula_page.runJavaScript("""
            var mjelement = document.getElementById('mathjax-container');
            mjelement.getElementsByTagName('svg')[0].outerHTML;
        """, lambda result: self.update_svg(xml_header + result.encode()))
        # print('olf svg: ', self.formula_svg)

    def update_svg(self, svg:bytes):
        with QMutexLocker(self.formula_queue_mutex):
            formula = self.formula_queue.pop(0)
            self.append_formula_svg(formula, svg)
            if len(self.formula_queue) > 0:
                formula = self.formula_queue[0]
                self.formula_page.setHtml(page_template.format(formula=formula), QUrl('file://'))

    def save_as_text(self, filename):
        with open(filename, 'wt') as f:
            for item in [self.item(i) for i in range(self.count())]:
                formula = item.data(self.FormulaRole)
                f.write('\[' + formula + '\]\n')

    def load_from_text(self, filename):
        print('opening: ', filename)
        with open(filename, 'rt') as f:
            formula_list = f.read().split('\]\n\[')
            print('equations: ', len(formula_list))
            if len(formula_list) > 0:
                formula_list[0] = formula_list[0].removeprefix('\[')
                formula_list[-1] = formula_list[-1].removesuffix('\]\n')
        for formula in formula_list:
            # FIXME should we clear this first? or do we append to what is currently loaded?
            self.append_formula(formula)
            print('calling append: ', formula)

    def append_formula(self, formula:str):
        if formula:
            print('appending formula: acquiring mutex', formula)
            with QMutexLocker(self.formula_queue_mutex):
                # a mutex might be overkill here, since we don't have any explicit threads
                # so really we should never hang up here waiting for it.
                print('locked formula_queue_mutex')
                self.formula_queue.append(formula)
                if len(self.formula_queue) == 1:
                    # page loadFinished processing is not guaranteed to complete before a new page
                    # is called, so we only call setHtml here to kick off the processing if it
                    # if the formula at this scope is the only one waiting in the queue.  Otherwise
                    # update_svg will kick off the next one after the previous one is finished
                    # processing .
                    self.formula_page.setHtml(page_template.format(formula=formula), QUrl('file://'))
                else:
                    print('formula_queue processing elsewhere, moving on')
    # need to build menu:
    # associate actions/descriptions/methods, not necessarily using triggered.connect: dict?
    # Qaction->function,  method->text, Qaction->text
    # place them in a structured menu:

    copy_menu_struct = (('Preferred Default', copyDefault),
                         ('Image via (Qt)', copyImage),
                         ('Equation Text', copyEquation),
                         ('Image from temporary file', copyImageTmp),
                         ('SVG', copySvg),
                         ('SVG Text', copySvgText),
                         ('Other Formats', (('PDF', lambda: None),
                                            ('placeholder', lambda: None))),
                         ('More Temporary Files', (('Temp PDF File', lambda: None),
                                                   ('Temp PNG File', lambda: None),
                                                   ('Temp PS File', lambda: None)))
                        )

    '''
   Default
Simple Image via Qt
HTML Fragment (PNG)
PNG
Copy to Adobe InDesign
Effcts>
More HTML fragments>
    HTML Fragment (PNG), as text
    HTML fragment (SVG/PNG)
    HTML fragment (SVG)
    HTML fragment (temp. PNG file)
Specific Formats >
    PDF
    PNG
    EPS
    LaTeX source
    OpenOffice Draw
    GIF via ImageMagick's convert
    SVG via Inkscape
    WMV via inkscape
    EMF via inksape
    SVG via dvisvgm
Temporary File >
    Temp PDF File
    TEmp PNG File
    TEMP PS File
    '''


    def init_action_dicts(self):
        self.act_desc = {}
        self.act_meth = {}
        self.meth_act = {}

        stack = list(self.copy_menu_struct)
        # This while loop flattens the nested structured menu definition.  Using a stack makes
        # recursion unnecessary here.
        logging.debug(stack)
        while stack:
            logging.debug('init_action_dicts: loop')
            tmp = stack.pop(0)
            description, value = tmp

            if isinstance(value, (list, tuple)):
                stack.extend(value)
            else:
                action = QAction(description)
                self.act_desc[action] = description
                self.act_meth[action] = value
                self.meth_act[value] = action

    def build_copy_menu(self, group:QActionGroup=None, checkable:bool=True):
        return build_menu(self.copy_menu_struct, group, checkable=checkable)


