import logging, sys, os
from functools import partial
from enum import Enum, StrEnum
from PyQt5.QtWidgets import (qApp, QAction, QActionGroup, QListWidget, QLabel, QSizePolicy,
                             QAbstractItemView, QListWidgetItem, QMenu, QStyle, QStyledItemDelegate)
from PyQt5.QtCore import (pyqtSignal, QDir, Qt, QMimeData, QMutex, QMutexLocker, QRectF, QSettings, QSize,
                          QTemporaryFile, QUrl, QAbstractListModel)
from PyQt5.QtGui import QPalette, QCursor, QIcon, QImage, QPainter, QPixmap, QColor
from PyQt5.QtSvg import QSvgWidget, QSvgRenderer
from PyQt5.QtWebEngineWidgets import QWebEnginePage
from mjrender import (context, mathjax_v2_url, mathjax_url_remote, mathjax_url, mathjax_v2_config,
                      mathjax_config, page_template)

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
    FormulaData = namedtuple('FormulaData', ('svg_data', 'renderer'))
    SvgRole = Qt.UserRole
    FormulaRole = Qt.UserRole + 1
    SvgWidgetRole = Qt.UserRole + 2

    settings = QSettings()
    item_ops = set()
    # This creates a class level method decorator that registers a decorated method to a set
    register = partial(lambda s, e: (s.add(e) or e), item_ops)



    def __init__(self, parent=None, formulas=[]):
        super().__init__(parent)
        self.tempfiles = []
        self.formula_queue = [] # should this be a deque ?
        self.init_action_dicts()
        self.formula_queue_mutex = QMutex()
        self.clipboard = qApp.clipboard()

        self.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.setUniformItemSizes(False)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragDropMode(QAbstractItemView.InternalMove)
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
        self.itemDoubleClicked.connect(self.editItem)
        self.delegate = FormulaDelegate()
        self.setItemDelegate(self.delegate)
    @classmethod
    def setSettings(cls, settings:QSettings):
        # maybe totally unecessary
        cls.settings = settings

    def itemChanged(self):

        for item in [self.item(i) for i in range(self.count())]:
            svg_widget = self.itemWidget(item)
            if item.isSelected():
                ...

            else:
                ...


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

    @register
    def copySvg(self, index):

        item = self.item(index)
        rec = item.data(Qt.UserRole)
        svg = rec.svg_data

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
        rec = item.data(Qt.UserRole)
        svg = rec.svg_data
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
        # item.setData(self.FormulaRole, formula)
        item.setText(formula)

        renderer = QSvgRenderer()
        renderer.load(svg)
        renderer.setViewBox(renderer.viewBox().adjusted(0, -200, 0, 200))
        renderer.setAspectRatioMode(Qt.KeepAspectRatio)
        rec = self.FormulaData(svg, renderer)
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

        # item.setData(FormulaList.SvgWidgetRole, svg_widget)
        self.addItem(item)
        # self.setItemWidget(item, svg_widget)

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
                # formula = item.data(self.FormulaRole)
                formula = item.text()
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



class FormulaListItem(QListWidgetItem):
    #def __init__(self, *args, value: typing.Any=None, **kwargs):
    '''
    QListWidgetItem(parent: typing.Optional[QListWidget] = None, type: int = QListWidgetItem.Type)
    QListWidgetItem(text: str, parent: typing.Optional[QListWidget] = None, type: int = QListWidgetItem.Type)
    QListWidgetItem(icon: QIcon, text: str, parent: typing.Optional[QListWidget] = None, type: int = QListWidgetItem.Type)
    QListWidgetItem(other: QListWidgetItem)
    
    '''
    @overload
    def __init__(self, parent: typing.Optional[QListWidget] = None,
                 type: int = QListWidgetItem.UserType):
        super().__init__(parent, type)
    @overload
    def __init__(self, text: str, parent: typing.Optional[QListWidget] = None,
                 type: int = QListWidgetItem.UserType):
        super().__init__(text, parent, type)
    @overload
    def __init__(self, icon: QIcon, text: str, parent: typing.Optional[QListWidget] = None,
                 type: int = QListWidgetItem.Type):
        super().__init__(icon, text, parent, type)

    @overload
    def __init__(self, other: QListWidgetItem):
        super().__init__(other)
        ...
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)




class FormulaDelegate(QStyledItemDelegate):

    def __init__(self, parent=None):
        super().__init__(parent)

    def paint(self, painter, option, index):

        #svg = index.data(FormulaList.SvgRole)
        rec = index.data(Qt.UserRole)
        renderer = rec.renderer
        svg = rec.svg_data

        # later we should check option.state and render differently if selected
        if option.state & QStyle.State_Selected:
            fill_color = option.palette.highlight().color()
            draw_color_str = option.palette.color(QPalette.Active, QPalette.HighlightedText).name()
            painter.setBrush(option.palette.highlightedText()) #seems to do nothing
            painter.fillRect(QRectF(option.rect), fill_color)

        else:
            fill_color = option.palette.color(QPalette.Active, QPalette.Base)
            # draw_color_str = option.palette.text().color().name() # this color is too light
            draw_color_str = QColor(QPalette.Text).name() # using hard coded Text color instead
            painter.setBrush(option.palette.windowText()) # this seems to not affect SVG rendering

        logging.debug('fill_color: {}'.format(fill_color))
        logging.debug('draw_color_str: {}'.format(draw_color_str))

        # renderer.load(svg)
        renderer.load(svg.replace(b'currentColor', draw_color_str.encode()))
        renderer.setAspectRatioMode(Qt.KeepAspectRatio)
        renderer.setViewBox(renderer.viewBox().adjusted(0, -200, 0, 200))

        painter.save()
        renderer.render(painter, QRectF(option.rect))
        painter.restore()

        # else:
        #     QStyledItemDelegate.paint(self, painter, option, index)

    def sizeHint(self, option, index):

        rec = index.data(Qt.UserRole)
        renderer = rec.renderer
        svg = rec.svg_data

        #!renderer().viewBox().adjusted(0, -200, 0, 200))

        if not rec.renderer.isValid():
            renderer.load(svg.replace(b'currentColor', b'green'))
            renderer.setAspectRatioMode(Qt.KeepAspectRatio)
            renderer.setViewBox(renderer.viewBox().adjusted(0, -200, 0, 200))

        if renderer:
            hint = renderer.defaultSize() / 24
        else:
            hint = QStyledItemDelegate.sizeHint(self, option, index)

        data = index.data()
        logging.debug('delegate: formula = {}'.format(data))
        logging.debug('delegate sizeHint: {}'.format(hint))
        # look at renderer.defaultSize
        return hint


    # def createEditor(self, parent, option, index):
    #     """ Creates and returns the custom StarEditor object we'll use to edit
    #         the StarRating.
    #     """
    #     if index.column() == 3:
    #         editor = StarEditor(parent)
    #         editor.editing_finished.connect(self.commit_and_close_editor)
    #         return editor
    #     else:
    #         return QStyledItemDelegate.createEditor(self, parent, option, index)

    # def setEditorData(self, editor, index):
    #     """ Sets the data to be displayed and edited by our custom editor. """
    #     if index.column() == 3:
    #         editor.star_rating = StarRating(index.data())
    #     else:
    #         QStyledItemDelegate.setEditorData(self, editor, index)

    # def setModelData(self, editor, model, index):
    #     """ Get the data from our custom editor and stuffs it into the model.
    #     """
    #     if index.column() == 3:
    #         model.setData(index, editor.star_rating.star_count)
    #     else:
    #         QStyledItemDelegate.setModelData(self, editor, model, index)

    # def commit_and_close_editor(self):
    #     """ Erm... commits the data and closes the editor. :) """
    #     editor = self.sender()

    #     # The commitData signal must be emitted when we've finished editing
    #     # and need to write our changed back to the model.
    #     self.commitData.emit(editor)
    #     self.closeEditor.emit(editor, QStyledItemDelegate.NoHint)

