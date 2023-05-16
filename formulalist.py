import logging, sys, os
from functools import partial
from enum import Enum, StrEnum
from PyQt5.QtWidgets import (qApp, QAction, QActionGroup, QApplication, QListWidget, QLabel,
                             QSizePolicy, QAbstractItemView, QListWidgetItem, QMenu, QPlainTextEdit,
                             QStyle, QStyledItemDelegate, QWidget)
from PyQt5.QtCore import (pyqtProperty, pyqtSignal, pyqtSlot, QCoreApplication, QDir, QEvent,
                          QEventLoop, Qt, QMimeData, QMutex, QMutexLocker, QObject, QPoint, QRectF,
                          QSettings, QSize, QTemporaryFile, QUrl, QAbstractListModel, QVariant,
                          QWaitCondition, QPersistentModelIndex, QModelIndex)
from PyQt5.QtGui import QPalette, QCursor, QIcon, QImage, QPainter, QPixmap, QColor
from PyQt5.QtSvg import QSvgWidget, QSvgRenderer
from PyQt5.QtWebEngineWidgets import QWebEnginePage
from PyQt5.QtWebChannel import QWebChannel
from mjrender import (context, mathjax_v2_url, mathjax_v3_url, mathjax_v3_url_remote,
                      mathjax_v2_config, mathjax_v3_config, page_template, javascript_v2_extract,
                      javascript_v3_extract, qchannel_js, mj_enqueue, gen_render_html,
                      CallHandler, MathJaxRenderer)

from texsyntax import LatexHighlighter

from time import perf_counter, sleep

import matplotlib.pyplot as plt
plt.rc('mathtext', fontset='cm')

from menubuilder import build_menu, disable_unused_submenus
from collections import namedtuple

from io import BytesIO
import typing
from typing import overload
class CopyProfile(StrEnum):
    SVG = 'SVG'
    SVG_TEXT = 'SVG Text'
    IMG = 'Image'
    IMG_TMP = 'Temporary Image File'
    EQ = 'Latex Equation'

# settings = QSettings(QCoreApplication.organizationName(), QCoreApplication.applicationName())
settings = QSettings()



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

FormulaData = namedtuple('FormulaData', ('svg_data', 'renderer'))




class FormulaList(QListWidget):
    item_ops = set()
    # This creates a class level method decorator that registers a decorated method to a set
    register = partial(lambda s, e: (s.add(e) or e), item_ops)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tempfiles = []
        self.formula_queue = [] # should this be a deque ?
        self.init_action_dicts()
        self.formula_queue_mutex = QMutex()
        self.clipboard = qApp.clipboard()

        self.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.setUniformItemSizes(False)
        self.setSpacing(1)

        self.setViewMode(QListWidget.ListMode)
        # self.formula_page = QWebEnginePage()
        # self.formula_page.loadFinished.connect(self._on_load_finished)

        # html = gen_render_html()
        # self.formula_page.setHtml(html, QUrl('file://'))

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
        # XXX check if this editItem is necessary.
        #self.itemDoubleClicked.connect(self.editItem)
        self.delegate = FormulaDelegate(self)
        self.setItemDelegate(self.delegate)
        self.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setAcceptDrops(True)
        self.setDefaultDropAction(Qt.MoveAction)

        # self.channel = QWebChannel()
        self.mj_renderer = MathJaxRenderer()
        self.mj_renderer.formulaProcessed.connect(self.append_formula_svg)
        #self.installEventFilter(self)


    @classmethod
    def setSettings(cls, settings:QSettings):
        # maybe totally unecessary
        cls.settings = settings

    @pyqtSlot()
    def itemChanged(self):

        for item in [self.item(i) for i in range(self.count())]:
            svg_widget = self.itemWidget(item)
            if item.isSelected():
                ...

            else:
                ...


    @pyqtSlot(QPoint)
    def listContextMenuRequested(self, pos):
        # pos = self.mapFromGlobal(QCursor.pos()) # I don't think this is necessary now
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

    @register
    def copySvg(self, index):

        item = self.item(index)
        rec = item.data(Qt.UserRole)
        svg = rec.svg_data

        # create a QMimeData object and set the SVG data
        mime_data = QMimeData()
        # mime_data.setData("image/svg+xml", self.images[index])
        mime_data.setData("image/svg", svg.replace(b'currentColor', b'red')) # works for Anki

        # mime_data.setData("image/svg+xml", self.images[index].replace(b'currentColor', b'red'))
        # mime_data.setData("image/svg+xml"
        # mime_data.setData("image/svg"

        # get the system clipboard and set the QMimeData object
        self.clipboard.setMimeData(mime_data)

        if self.clipboard.mimeData().hasImage():
            ...

    @register
    def copySvgText(self, index):

        item = self.item(index)
        rec = item.data(Qt.UserRole)
        svg = rec.svg_data
        qApp.clipboard().setText(svg.decode())


    @register
    def copyImage(self, index):

        image = self.genPngByIndex(index)
        self.clipboard.setImage(image)
        logging.debug(f'copyImage called {index}')

    def genPngByIndex(self, index):

        rfactor = settings.value("copyImage/reductionFactor", 12.0, type=float)
        # eventually i want to make this a more intutive setting, something related to
        # dpi  # i think a ratio of 12 may be very close to 600dpi
        # so then a ratio of 6 would be 1200 dpi, 24 would be 300, 48: 150

        item = self.item(index)
        rec = item.data(Qt.UserRole)
        svg = rec.svg_data

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
        formula = item.text()

        qApp.clipboard().setText(formula)

        logging.debug(f'copyEquation called {formula}')

    # setting class default copy behavior
    copyDefault = copyEquation

    def copy(self):
        try:
            row = self.selectedIndexes()[0].row()
        except (IndexError, AttributeError):
            row = -1
        else:
            if row >= 0:
                logging.debug('in copy')
                self.copyDefault(row)


    @classmethod
    def setCopyDefault(cls, method):

        cls.copyDefault = method

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
        item.setFlags(
            Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled)
        item.setText(formula)

        renderer = QSvgRenderer()
        renderer.load(svg)
        renderer.setViewBox(renderer.viewBox().adjusted(0, -200, 0, 200))
        renderer.setAspectRatioMode(Qt.KeepAspectRatio)
        rec = FormulaData(svg, None)
        item.setData(Qt.UserRole, rec)

        # self.formulas.append(formula)
        # self.images.append(svg)
        # svg_widget = QSvgWidget()

        # This can replace the color in the svg data
        # svg = svg.replace(b'currentColor', b'red')

        #svg_widget.load(svg)
        # save this for size adjustment
        #!svg_widget.renderer().setAspectRatioMode(Qt.KeepAspectRatio)
        #!svg_widget.renderer().setViewBox(svg_widget.renderer().viewBox().adjusted(0, -200, 0, 200))
        #!svg_widget.setFixedHeight( svg_widget.renderer().defaultSize().height() // 24)

        # effectively adds padding around the QSvgWidget
        # print("view box: ", svg_widget.renderer().viewBox())

        # print("sfh resized: ", svg_widget.renderer().defaultSize().height())
        policy = QSizePolicy()
        policy.setVerticalPolicy(QSizePolicy.Fixed)

        # print('svg sizeHint: ', svg_widget.sizeHint())

        # print('svg_widget size hint: ', svg_widget.sizeHint())
        # item.setContentsMargins(0, 5, 0, 5)  #no effect?
        # item.setSizeHint(QSize(0, svg_widget.renderer().defaultSize().height() // 24))

        self.addItem(item)
        # self.setItemWidget(item, svg_widget)

        self.scrollToBottom()


    def _on_load_finished(self):
        # Extract the SVG output from the page and add an XML header
        xml_header = b'<?xml version="1.0" encoding="utf-8" standalone="no"?>'
        mathjax_ver = settings.value("main/mathjaxVersion", '3', type=str)

        if mathjax_ver == '2':
            # self.formula_page.runJavaScript(javascript_v3_extract,
            #                                 lambda result: self.update_svg(
            #                                     xml_header + result.encode()))
            #self.formula_page.runJavaScript("""
            #document.getElementsByTagName('mathjax')[0].outerHTML;""",
            #partial(print, 'Load finished XXXXX'))
            self.formula_page.runJavaScript(mj_enqueue,
                                            partial(print, 'Load finished ZZZZ'))
        elif mathjax_ver == '3':
            self.formula_page.runJavaScript(javascript_v3_extract,
                                            lambda result: self.update_svg(
                                                xml_header + result.encode()))
        else:
            self.formula_page.runJavaScript("""
                var mjelement = document.getElementById('mathjax-container');
                mjelement.getElementsByTagName('svg')[0].outerHTML;
            """, lambda result: self.update_svg(xml_header + result.encode()))

    def update_svg(self, svg:bytes):
        with QMutexLocker(self.formula_queue_mutex):
            formula = self.formula_queue.pop(0)
            self.append_formula_svg(formula, svg)
            if len(self.formula_queue) > 0:
                formula = self.formula_queue[0]
                html = gen_render_html()
                # self.formula_page.setHtml(html.format(formula=formula), QUrl('file://'))

    def save_as_text(self, filename):
        with open(filename, 'wt') as f:
            for item in [self.item(i) for i in range(self.count())]:
                formula = item.text()
                f.write('\[' + formula + '\]\n')

    def load_from_text(self, filename):
        with open(filename, 'rt') as f:
            formula_list = f.read().split('\]\n\[')
            if len(formula_list) > 0:
                formula_list[0] = formula_list[0].removeprefix('\[')
                formula_list[-1] = formula_list[-1].removesuffix('\]\n')
        for formula in formula_list:
            # FIXME should we clear this first? or do we append to what is currently loaded?
            self.append_formula(formula)

    def append_formula(self, formula:str):
        if formula:
            self.mj_renderer.submitFormula(formula)
            return

    # this is the menu structure for building copy methods menus.  It gets fed into build_menu
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



    def init_action_dicts(self):
        self.act_desc = {}
        self.act_meth = {}
        self.meth_act = {}

        stack = list(self.copy_menu_struct)
        # This while loop flattens the nested structured menu definition.  Using a stack makes
        # recursion unnecessary here.
        logging.debug(stack)
        while stack:
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



class FormulaDelegate(QStyledItemDelegate):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.installEventFilter(self)
        self.renderer = QSvgRenderer()
        self.editor_ref = None
        self.editor_sizeHint = QSize(0,0)
        self.currently_editing_item = None

    def paint(self, painter, option, index):

        rec = index.data(Qt.UserRole)
        # renderer = self.renderer
        if rec is not None and rec.svg_data is not None:
            svg = rec.svg_data
            # later we should check option.state and render differently if selected
            if option.state & QStyle.State_Selected:
                bg_color = option.palette.highlight().color()
                draw_color = option.palette.color(QPalette.Active, QPalette.HighlightedText)
                painter.setBrush(option.palette.highlightedText()) #seems to do nothing
                painter.fillRect(QRectF(option.rect), bg_color)

            else:
                bg_color = option.palette.color(QPalette.Active, QPalette.Base)
                # draw_color = option.palette.text().color() # this color is too light
                draw_color = QColor(QPalette.Text) # using hard coded Text color instead
                painter.setBrush(option.palette.windowText()) # this seems to not affect SVG rendering

            logging.debug('bg_color.name(): {}'.format(bg_color.name()))
            logging.debug('draw_color.name(): {}'.format(draw_color.name()))

            vpad = settings.value("display/verticalPadding", 200, type=int)
            # renderer.load(svg)
            self.renderer.load(svg.replace(b'currentColor', draw_color.name().encode()))
            self.renderer.setAspectRatioMode(Qt.KeepAspectRatio)
            self.renderer.setViewBox(self.renderer.viewBox().adjusted(0, -vpad, 0, vpad))

            painter.save()
            self.renderer.render(painter, QRectF(option.rect))
            painter.restore()

        else:
            return super().paint(painter, option, index)
        #     QStyledItemDelegate.paint(self, painter, option, index)


    def sizeHint(self, option, index):

        rec = index.data(Qt.UserRole)
        parent:FormulaList = self.parent()

        persistent = QPersistentModelIndex(index)

        if parent.state() == QAbstractItemView.EditingState:
            persistent = self.editor_ref.index
            open_index = persistent.model().index(persistent.row(), persistent.column(),
                                                  persistent.parent())

        if parent.state() == QAbstractItemView.EditingState and self.editing_index.row() == index.row():
            hint = self.editor_ref.sizeHint()
            return hint
        elif rec is not None:
            svg = rec.svg_data
            self.renderer.load(svg)
            self.renderer.setAspectRatioMode(Qt.KeepAspectRatio)

            vpad = settings.value("display/verticalPadding", 200, type=int)
            rfactor = settings.value("display/reductionFactor", 24, type=float)

            self.renderer.setViewBox(self.renderer.viewBox().adjusted(0, -vpad, 0, vpad))

            if self.renderer:
                logging.debug('delegate: basing size on renderer')
                hint = self.renderer.defaultSize() / rfactor
            else:
                hint = QStyledItemDelegate.sizeHint(self, option, index)

            logging.debug('otherwise: {}'.format(QStyledItemDelegate.sizeHint(self, option, index)))

            data = index.data()
            logging.debug('delegate: rfactor = {}'.format(rfactor))
            logging.debug('delegate: vpad {}'.format(vpad))
            logging.debug('delegate: formula = {}'.format(data))
            logging.debug('delegate sizeHint: {}'.format(hint))
            # look at renderer.defaultSize
            return hint
        else:
            return QSize(500, 500)
            #return super().sizeHint(option, index)



    def createEditor(self, parent:QListWidget, option, index):
        #     """ Creates and returns the custom StarEditor object we'll use to edit
        #         the StarRating.
        #     """
        #
        # https://stackoverflow.com/questions/71358160/qt-update-view-size-on-delegate-sizehint-change

        editor = FormulaEdit(parent)
        self.editor_ref = editor
        editor.editingFinished.connect(self.commit_and_close_editor)

        persistent = QPersistentModelIndex(index)
        def emitSizeHintChanged():
            index = persistent.model().index(persistent.row(), persistent.column(),
                                             persistent.parent())
            self.sizeHintChanged.emit(index)
        editor.sizeHintChanged.connect(emitSizeHintChanged)
        # editor.index = QPersistentModelIndex(index)
        editor.updateIndexThing(QPersistentModelIndex(index), index)
        self.sizeHintChanged.emit(index)
        self.editor_sizeHint = editor.sizeHint()
        # XXThis didn't work, but maybe it could
        index.model().layoutChanged.emit()
        self.parent().scrollTo(index)


        return editor
        #     else:
        #         return QStyledItemDelegate.createEditor(self, parent, option, index)

    def setEditorData(self, editor, index):
        self.editing_index = index
        self.editing_index_persistent = QPersistentModelIndex(index)
        """ Sets the data to be displayed and edited by our custom editor. """

        if index:
            formula = index.data() or ''
            editor.input_box.setPlainText(formula)
            # editor.updatePreview() # the above line should generate this signal
        else:
            QStyledItemDelegate.setEditorData(self, editor, index)

        #     if index.column() == 3:
        #         editor.star_rating = StarRating(index.data())
        #     else:
        #         QStyledItemDelegate.setEditorData(self, editor, index)

    def setModelData(self, editor, model, index):
        """ Get the data from our custom editor and stuffs it into the model.
        """

        # retrieve formula
        formula, svg_data = editor.getFormulaData()
        rec = FormulaData(svg_data, None)


        #editor.input_box.setFocus()
        model.setData(index, editor.formula)
        model.setData(index, rec, Qt.UserRole)

        '''
        # retreive and encapsulate SVG data
        rec = FormulaData(editor.svg_data, editor.formula)
        model.setData(index, rec, Qt.UserRole)
        print(editor.svg_data.decode())
        '''


        #     if index.column() == 3:
        #         model.setData(index, editor.star_rating.star_count)
        #     else:
        #         QStyledItemDelegate.setModelData(self, editor, model, index)


    @pyqtSlot()
    def commit_and_close_editor(self):
        """ Erm... commits the data and closes the editor. :) """
        print('commit_and_close_editor called')
        editor = self.sender()

        # The commitData signal must be emitted when we've finished editing
        # and need to write our changed back to the model.
        self.commitData.emit(editor)
        #XXXX maybe the real problem is that the editor is gettign closed and so the signals never
        # process or are received.  maybe we need to verify that they are processed before
        # closeEditor is called.
        # self.closeEditor.emit(editor, QStyledItemDelegate.NoHint)
        #self.closeEditor.emit(editor, QStyledItemDelegate.EditNextItem)
        self.currently_editing_item = None
        self.closeEditor.emit(editor, QStyledItemDelegate.NoHint)
        self.editor_ref = None
        # QStyledItemDelegate.EditNextItem

    def updateEditorGeometry(self, editor, option, index:QModelIndex):
        rect = option.rect;
        sizeHint = editor.sizeHint();
        if (rect.height() < sizeHint.height()):
            rect.setHeight(sizeHint.height())

        # if (rect.width()<sizeHint.width()) rect.setWidth(sizeHint.width());
        # editor->setGeometry(rect);

        editor.setGeometry(rect)

    def eventFilter(self, editor, event:QEvent):
        if event.type() == event.LayoutRequest:

            persistent = editor.index
            index = persistent.model().index(persistent.row(), persistent.column(),
                                             persistent.parent())
            self.sizeHintChanged.emit(index)
        return super().eventFilter(editor, event)

from ui.settings_ui import Ui_settings
from ui.formulaedit_ui import Ui_FormulaEdit

# how to prevent closing of editor i think
# https://stackoverflow.com/questions/54623332/qtableview-prevent-departure-from-cell-and-closure-of-delegate-editor

class FormulaEdit(QWidget, Ui_FormulaEdit):

    editingFinished = pyqtSignal()
    sizeHintChanged = pyqtSignal(QPersistentModelIndex)

    def __init__(self, parent=None):
        super().__init__(parent)


        self.initUI()
        self.svg_data = None
        self.formula = None
        self.preview.setPage(self.mj_renderer)
        self.input_box.textChanged.connect(self.updatePreview)
        self.mj_renderer.formulaProcessed.connect(self.setFormulaData)
        self.waitPreview = QMutex()
        self.previewUpdated = QWaitCondition()
        self.loop = QEventLoop(qApp)
        self.highlight = LatexHighlighter(self.input_box.document())
        # installing event filter on QPlainTextEdit seems to override Ctrl+Enter default behavior
        self.input_box.installEventFilter(self)
        # self.installEventFilter(self)

    def initUI(self):
        self.setupUi(self)
        self.mj_renderer = MathJaxRenderer()
        #self.mj_renderer.formulaProcessed.connect(X)
        self.preview.setPage(self.mj_renderer)
        self.input_box.setFocus()
        self.input_box.grabKeyboard()
        self.setAutoFillBackground(True)

    def updateIndexThing(self, index, oindex):
        self.index = index
        self.oindex = index
        self.sizeHintChanged.emit(self.index)

    @pyqtSlot(str, bytes)
    def setFormulaData(self, formula:str, svg_data:bytes):
        self.formula = formula
        self.svg_data = svg_data
        print('setFormulaData: formula data updating')
        self.input_box.setUpdatesEnabled(True)

        if self.loop.isRunning():
            self.loop.quit()
        else:
            ...
        # self.waitPreview.unlock()

    def prepareFormulaData(self):
        # self.setEnabled(False)  # disable editor while processing
        formula = self.input_box.toPlainText()
        self.mj_renderer.submitFormula(formula)
        # qApp.processEvents()
        #while self.svg_data is None:
        #    #QApplication.processEvents()
        #    qApp.processEvents()
        #    sleep(0.1)
        if self.svg_data is None:
            if hasattr(self.mj_renderer.handler, 'svg_data'):
                ...
            else:
                ...
            self.loop.exec()
        # self.setEnabled(True)  # disable editor while processing
    def getFormulaData(self):
        return self.formula, self.svg_data

    # def editingFinished(self):
    #     return self.formula is not None


    def eventFilter(self, obj, event):

        if event.type() == QEvent.KeyPress: # and obj is self:

            if event.key() in {Qt.Key_Return, Qt.Key_Enter}:
                if event.modifiers() & Qt.ControlModifier:
                    self.prepareFormulaData()
                    self.editingFinished.emit()
                    return True
                elif event.modifiers() & Qt.ShiftModifier:
                    return True
            elif event.key() == Qt.Key_Escape:
                return False

        return False

    def eventFilter_disabled(self, obj, event):
        if obj is self.input_box and event.type() == QEvent.FocusIn:
            # Clear the input box when it receives focus
            # self.input_box.setPlainText('')
            ...

        if event.type() == QEvent.KeyPress and obj is self:

            if event.key() == Qt.Key_Return and self.input_box.hasFocus():
                if event.modifiers() & Qt.ControlModifier:
                    # disabling edits while svg renders, should be quick. Might reenable it s/w
                    # self.input_box.setUpdatesEnabled(False)
                    self.setEnabled(False)  # disable editor while processing
                    formula = self.input_box.toPlainText()
                    # self.waitPreview.lock()
                    self.mj_renderer.submitFormula(formula)
                    # self.previewUpdated.wait(self.waitPreview)
                    #reenable after formula comitted
                    ###XXXwill this change???
                    # self.commit_current_formula()
                    # return False# this seems to delete the trailing \n.. interesting
                    return True

        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Escape:
                return True

        return super().eventFilter(obj, event)

    @pyqtSlot()
    def updatePreview(self):
        formula = self.input_box.toPlainText()
        self.mj_renderer.updatePreview(formula)

    @pyqtSlot()
    def on_commit_formula_button_clicked(self):
        self.prepareFormulaData()
        self.editingFinished.emit()

