import logging, sys, os
from functools import partial
from enum import Enum, StrEnum
from PyQt5.QtWidgets import (qApp, QAbstractItemDelegate, QAction, QActionGroup, QListView,
                             QSizePolicy, QAbstractItemView, QListWidgetItem, QStyle,
                             QStyledItemDelegate, QWidget, QLineEdit)
from PyQt5.QtCore import (pyqtSignal, pyqtSlot, QAbstractItemModel, QDir, QEvent, QEventLoop, Qt,
                          QMimeData, QMutex, QMutexLocker, QObject, QPoint, QRectF, QSettings,
                          QSize, QTemporaryFile, QUrl, QWaitCondition, QPersistentModelIndex,
                          QModelIndex, QVariant)
from PyQt5.QtGui import QPalette, QImage, QPainter, QColor, QStandardItem, QStandardItemModel
from PyQt5.QtSvg import QSvgWidget, QSvgRenderer
from mjrender import javascript_v3_extract, mj_enqueue, gen_render_html, MathJaxRenderer

from texsyntax import LatexHighlighter

import matplotlib.pyplot as plt
plt.rc('mathtext', fontset='cm')

from menubuilder import build_menu, disable_unused_submenus
from collections import namedtuple

from io import BytesIO

# Move this to a modular debugging kit for PyQT.  Is there anything prebuilt that does this?
event_dict = {getattr(QEvent, v):v for v in dir(QEvent) if isinstance(getattr(QEvent, v), QEvent.Type)}

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




class FormulaView(QListView):
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

        self.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.setUniformItemSizes(False)
        self.setSpacing(1)

        self.setViewMode(QListView.ListMode)
        self.setResizeMode(QListView.Adjust)
        self.setModel(QStandardItemModel())

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
        self.delegate = FormulaDelegate(self)
        self.setItemDelegate(self.delegate)
        self.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setAcceptDrops(True)
        self.setDefaultDropAction(Qt.MoveAction)

        self.mj_renderer = MathJaxRenderer(self)
        self.mj_renderer.formulaProcessed.connect(self.append_formula_svg)
        self.installEventFilter(self)


    def eventFilter(self, object: QObject, event: QEvent) -> bool:
        ...

        if event.type() == QEvent.KeyPress:  # and obj is self:

            if event.key() == Qt.Key_Delete and event.modifiers() & Qt.ControlModifier:
                for index in self.selectedIndexes():
                    self.deleteEquation(index.row())

                return True

        return False

    def closeEditor(self, editor: QWidget, hint: QAbstractItemDelegate.EndEditHint) -> None:
        if not editor.delegate_processed:
            editor.editingAborted.emit()
            print('closeEditor: aborting')
        else:
            return super().closeEditor(editor, hint)

    def append_new_and_edit(self):
        index:QModelIndex = self.append_new()
        self.setCurrentIndex(index)
        self.edit(index)

    def append_new(self):
        item = QStandardItem()
        item.setFlags(Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsEnabled |
                      Qt.ItemIsDragEnabled)
        # item.setHidden(True)
        self.model().appendRow([item])
        index = item.index()

        return index

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
        if row < 0 and not self.selectedIndexes():
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
    def copySvg(self, row):

        item = self.model().item(row)
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
    def copySvgText(self, row):

        item = self.model().item(row)
        rec = item.data(Qt.UserRole)
        svg = rec.svg_data
        qApp.clipboard().setText(svg.decode())


    @register
    def copyImage(self, row):

        image = self.genPngByRow(row)
        self.clipboard.setImage(image)
        logging.debug(f'copyImage called {row}')

    def genPngByRow(self, row):

        rfactor = settings.value("copyImage/reductionFactor", 12.0, type=float)
        # eventually i want to make this a more intutive setting, something related to
        # dpi  # i think a ratio of 12 may be very close to 600dpi
        # so then a ratio of 6 would be 1200 dpi, 24 would be 300, 48: 150

        item = self.model().item(row)
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
    def copyImageTmp(self, row):

        image = self.genPngByRow(row)
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
    def copyEquation(self, row):

        item = self.model().item(row)
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
    def deleteEquation(self, row):
        # self.formulas.pop(index)
        # self.images.pop(index)
        self.model().removeRow(row)

    def append_formula_svg_matplotlib(self, formula):
        # self.formulas.append(formula)
        svg = QSvgWidget()
        svg_data = render_latex_as_svg(formula)
        svg.load(svg_data)
        svg.renderer().setAspectRatioMode(Qt.KeepAspectRatio)
        # svg.sizeHint() returns (460, 345)
        self.layout().addWidget(svg)

    def append_formula_svg(self, formula, svg:bytes):

        item = QStandardItem()
        item.setFlags(Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsEnabled |
                      Qt.ItemIsDragEnabled)
        item.setText(formula)

        rec = FormulaData(svg, None)
        item.setData(rec, Qt.UserRole)

        item = QStandardItem()
        item.setFlags(Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsEnabled |
                      Qt.ItemIsDragEnabled)
        # item.setHidden(True)
        self.model().appendRow([item])
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

    # This is the menu structure for building copy methods menus. It gets fed into build_menu
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
        self.index_editor_dict = {}
        self.renderer = QSvgRenderer()
        self.editor_ref = None
        self.editing_index = None
        self.closeEditor.connect(self.close_editor)

    def paint(self, painter, option, index):

        # model.layoutChanged.emit()
        # if parent.state() == QAbstractItemView.EditingState and self.editing_index.row() == index.row():
        if option.state & QStyle.State_Editing:
            print('paint: called, State_Editing')
            model = index.model()
            #XXXmodel.layoutChanged.emit()
            # self.sizeHintChanged.emit(index)
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
                draw_color = option.palette.text().color() # this color is too light
                #draw_color = QColor(QPalette.Text) # using hard coded Text color instead
                painter.setBrush(option.palette.windowText()) # this seems to not affect SVG rendering
                painter.fillRect(QRectF(option.rect), bg_color)

            logging.debug('bg_color.name(): {}'.format(bg_color.name()))
            logging.debug('draw_color.name(): {}'.format(draw_color.name()))

            vpad = settings.value("display/verticalPadding", 200, type=int)

            # this replace is dependent on the svg format.  Maybe we should transform it
            # at the soruce so we can adjust it easily with bytes.format.
            self.renderer.load(svg.replace(b'rgb(0%, 0%, 0%)', draw_color.name().encode()))
            self.renderer.setAspectRatioMode(Qt.KeepAspectRatio)
            height =  self.renderer.viewBox().height()
            vpad = int(height * 0.1) # don't like this as a percent..
            self.renderer.viewBox().adjusted(0, -vpad, 0, vpad)
            self.renderer.setViewBox(QRectF(self.renderer.viewBox().adjusted(0, -vpad, 0, vpad)))
            painter.save()
            self.renderer.render(painter, QRectF(option.rect))
            painter.restore()

        else:
            return super().paint(painter, option, index)

    def get_editor_from_index(self, index):
        return self.index_editor_dict.get(QPersistentModelIndex(index), None)

    def get_index_from_editor(self, editor):
        pindex = self.index_editor_dict.get(editor, None)

        if pindex:
            return pindex.model().index(pindex.row(), pindex.column(), pindex.parent())
        else:
            return None

    def associate_editor_index(self, editor, index):
        self.index_editor_dict[QPersistentModelIndex(index)] = editor
        self.index_editor_dict[editor] = QPersistentModelIndex(index)

    def disassociate_editor_index(self, editor, index):
        del self.index_editor_dict[QPersistentModelIndex(index)]
        del self.index_editor_dict[editor]



    def sizeHint(self, option, index):

        # this may do nothing. I think this was attempting to get the
        # QStyle.State_Editing flag set the way I expected it.
        self.initStyleOption(option, index)
        base_hint = super().sizeHint(option, index)
        viewport_hint = self.parent().maximumViewportSize()

        rec = index.data(Qt.UserRole)
        parent:FormulaView = self.parent()
        pindex = QPersistentModelIndex(index)

        # if parent.state() == QAbstractItemView.EditingState:

        # if option.state & QStyle.State_Editing: # <- this does not properly detect an item edit
        edit_override_hint = None
        if self.is_being_edited(index):
            editor = self.get_editor_from_index(index)
            # editor deletion by C++/Qt is not signaled in all cases. By catching RuntimeError, we
            # can determine whether to use the size of the SVG or editor widget as the hint.
            try:
                edit_override_hint = editor.sizeHint()
            except RuntimeError:
                edit_override_hint = None

        if edit_override_hint:
            return edit_override_hint
        elif rec is not None:
            svg = rec.svg_data
            self.renderer.load(svg)
            self.renderer.setAspectRatioMode(Qt.KeepAspectRatio)

            vpad = settings.value("display/verticalPadding", 200, type=int)
            rfactor = settings.value("display/reductionFactor", 24, type=float)

            ####self.renderer.setViewBox(self.renderer.viewBox().adjusted(0, -vpad, 0, vpad))

            if self.renderer:
                logging.debug('delegate: basing size on renderer')
                ###hint = self.renderer.defaultSize() / rfactor
                hint = self.renderer.defaultSize() * 4 #
                # this almost works.. maybe subtract a little
                print('sizeHint: base_hint', base_hint)
                print('sizeHint: hint (original):', hint)
                if hint.width() > viewport_hint.width():
                    hint = hint * (viewport_hint.width() / hint.width())
                print('sizeHint: hint (modified):', hint)
                #hint.setWidth(base_hint.width())
                # something is goign on.. maybe it doesn't always work
            else:
                hint = QStyledItemDelegate.sizeHint(self, option, index)

            logging.debug('otherwise: {}'.format(QStyledItemDelegate.sizeHint(self, option, index)))

            data = index.data()
            logging.debug('delegate: rfactor = {}'.format(rfactor))
            logging.debug('delegate: vpad {}'.format(vpad))
            logging.debug('delegate: formula = {}'.format(data))
            logging.debug('delegate sizeHint: {}'.format(hint))
            # look at renderer.defaultSize

            # if option.state & QStyle.State_Selected: # is this check broken too?
            return hint
        else:
            try:
                editor = self.get_editor_from_index(index)
                hint = editor.sizeHint()
                return hint
            except:
                # This seems to be happening when we first insert items, so it's probably not
                # an exceptional condition. Just need a sizeHint for a new empty item.
                hint = QSize(500, 900)
                return hint
            #return super().sizeHint(option, index)

    def is_being_edited(self, index):

        if self.get_editor_from_index(index):
            return True
        else:
            return False

    def createEditor(self, parent:QListView, option, index):
        """ Creates and returns the custom formula editor for inline editing.
        """

        if self.get_editor_from_index(index):
            print('createEditor: editor already open!!!')

        # https://stackoverflow.com/questions/71358160/qt-update-view-size-on-delegate-sizehint-change
        #if not option.state & QStyle.State_Editing:

        model = index.model()
        editor = FormulaEdit(parent)
        self.associate_editor_index(editor, index)
        editor.editingFinished.connect(self.commit_and_close_editor)
        editor.editingAborted.connect(self.abort_and_close_editor)
        pindex = QPersistentModelIndex(index)

        def emitSizeHintChanged():
            print('emitSizeChanged:')
            index = pindex.model().index(pindex.row(), pindex.column(), pindex.parent())
            self.sizeHintChanged.emit(index)

        editor.sizeHintChanged.connect(emitSizeHintChanged)
        editor.updateIndexThing(QPersistentModelIndex(index))
        self.sizeHintChanged.emit(index)
        # XXThis didn't work, but maybe it could
        model.layoutChanged.emit()
        self.parent().scrollTo(index)

        #model.dataChanged.emit()
        return editor

    def setEditorData(self, editor, index):
        """ Sets the data to be displayed and edited by our custom editor. """
        self.editing_index = QPersistentModelIndex(index)

        editor.updateIndexThing(self.editing_index)

        if index:
            formula = index.data() or ''
            editor.input_box.setPlainText(formula)
            self.sizeHintChanged.emit(index)
        else:
            super().setEditorData(editor, index)


    def setModelData(self, editor, model, index):
        """ Get the data from our custom editor and stuffs it into the model. """

        editor.prepareFormulaData()
        formula, svg_data = editor.getFormulaData()

        rec = FormulaData(svg_data, None)

        model.setData(index, editor.formula)
        model.setData(index, rec, Qt.UserRole)


    @pyqtSlot()
    def abort_and_close_editor(self):
        editor = self.sender()
        editor.delegate_processed = True
        self.closeEditor.emit(editor, QStyledItemDelegate.NoHint)

    @pyqtSlot()
    def commit_and_close_editor(self):
        """ Commits the data and closes the editor. """
        editor = self.sender()
        editor.delegate_processed = True

        index = self.get_index_from_editor(editor)

        # The commitData signal must be emitted when we've finished editing
        # and need to write our changed back to the model.
        if index.row() == index.model().rowCount() - 1:
            # append a new item and edit it if we're on the last row
            self.parent().append_new()
            self.commitData.emit(editor)
            self.closeEditor.emit(editor, QStyledItemDelegate.EditNextItem)
        else:
            self.commitData.emit(editor)
            self.closeEditor.emit(editor, QStyledItemDelegate.NoHint)

    #def editorEvent(self, event: QtCore.QEvent, model: QtCore.QAbstractItemModel, option: 'QStyleOptionViewItem', index: QtCore.QModelIndex) -> bool:

    #def closeEditor(self, editor: QWidget, hint: QAbstractItemDelegate.EndEditHint) -> None:
    #@pyqtSlot(QWidget, QAbstractItemDelegate.EndEditHint)
    def close_editor(self, editor:QWidget, hint=QAbstractItemDelegate.NoHint) -> None:
        #shouldn't need to do this again I think
        #self.closeEditor.emit(editor, QStyledItemDelegate.NoHint)
        # how can we get this? closeEditor signal has editor & hint

        index = self.get_index_from_editor(editor)
        # this slot is being double classed.. tried to add a specific pyqtSlot to fix it
        # but couldn't figure out the type
        if index is not None:
            model = index.model()
            # why would index be a none here? maybe it got called after disassociating?

            self.disassociate_editor_index(editor, index)
            if model.rowCount() == index.row() + 1 and index.data() is None:
                model.removeRow(index.row())
            else:
                self.sizeHintChanged.emit(index)

            model.layoutChanged.emit()
        else:
            print('###########################################')
            print('close_editor: index is none')
            print('###########################################')

    def updateEditorGeometry(self, editor, option, index:QModelIndex):
        rect = option.rect;
        sizeHint = editor.sizeHint();
        if (rect.height() < sizeHint.height()):
            rect.setHeight(sizeHint.height())

        editor.setGeometry(rect)

    def eventFilter(self, editor, event: QEvent):
        if event.type() == event.LayoutRequest:

            pindex = self.get_index_from_editor(editor)
            index = pindex.model().index(pindex.row(), pindex.column(), pindex.parent())
            self.sizeHintChanged.emit(index)

        elif event.type() == QEvent.KeyPress:  # and obj is self:
            if event.key() == Qt.Key_Escape:
                index = self.get_index_from_editor(editor)
                if index:
                    self.closeEditor.emit(editor, QStyledItemDelegate.NoHint)  # method of delegate
                    return True

        # This doesn't work quite right, maybe do it in the editor eventFilter?
        # elif event.type() == QEvent.FocusOut:  # must be some other event
        #     index = self.get_index_from_editor(editor)
        #     model = index.model()
        #     self.closeEditor.emit(editor, QStyledItemDelegate.NoHint) # method of delegate
        #     return True

        # Trying to prevent editor close on losing focus
        elif event.type() in {QEvent.FocusAboutToChange, QEvent.FocusOut}:
            print('FocusAboutToChange/FocusOut')
            return True

        return super().eventFilter(editor, event)


from ui.settings_ui import Ui_settings
from ui.formulaedit_ui import Ui_FormulaEdit

# how to prevent closing of editor i think
# https://stackoverflow.com/questions/54623332/qtableview-prevent-departure-from-cell-and-closure-of-delegate-editor

class FormulaEdit(QWidget, Ui_FormulaEdit):

    editingFinished = pyqtSignal()
    editingAborted = pyqtSignal()
    sizeHintChanged = pyqtSignal(QPersistentModelIndex)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.initUI()
        self.delegate_processed = False
        self.svg_data = None
        self.formula = None
        ###self.preview.setPage(self.mj_renderer)
        self.input_box.textChanged.connect(self.updatePreview)
        self.mj_renderer.formulaProcessed.connect(self.setFormulaData)
        self.waitPreview = QMutex()
        self.previewUpdated = QWaitCondition()
        self.loop = QEventLoop(qApp)
        self.highlight = LatexHighlighter(self.input_box.document())
        # installing event filter on QPlainTextEdit seems to override Ctrl+Enter default behavior
        self.input_box.installEventFilter(self)
        # self.installEventFilter(self)
        self.input_box.textChanged.connect(lambda: self.sizeHintChanged.emit(self.index))
        self.setFocusPolicy(Qt.StrongFocus)

    def initUI(self):
        self.setupUi(self)
        self.mj_renderer = MathJaxRenderer(self)
        #self.mj_renderer.formulaProcessed.connect(X)
        self.preview.setPage(self.mj_renderer)
        self.input_box.setFocus()
        self.input_box.grabKeyboard()
        self.setAutoFillBackground(True)

    def updateIndexThing(self, index):
        self.index = index
        self.sizeHintChanged.emit(self.index)

    @pyqtSlot(str, bytes)
    def setFormulaData(self, formula:str, svg_data:bytes):
        self.formula = formula
        self.svg_data = svg_data
        print('setFormulaData: formula data updating')
        # self.input_box.setUpdatesEnabled(True)

        if self.loop.isRunning():
            self.loop.quit()
        else:
            ...
        # self.waitPreview.unlock()

    def prepareFormulaData(self):
        # self.setEnabled(False)  # disable editor while processing
        formula = self.input_box.toPlainText()
        self.mj_renderer.submitFormula(formula)
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
                    self.editingFinished.emit()
                    return True
                elif event.modifiers() & Qt.ShiftModifier:
                    return True
            elif event.key() == Qt.Key_Escape:
                # maybe just send a signal or sth to remove the item, and that it was abandoned
                # self.closeEditor.emit() # method of delegate
                return False
            # elif event.key() == Qt.Key_U:
            #     self.size_hint_inc()
            #     return False
            # elif event.key() == Qt.Key_D:
            #     self.size_hint_dec()
            #     return False

        # elif event.type() == QEvent.FocusOut:  # must be some other event
        #     self.editingAborted.emit()
        #     return True

        return False
        # return super().eventFilter(obj, event)

    def size_hint_inc(self):
        if not hasattr(self, 'size_hint_override'):
            self.size_hint_override = super().sizeHint()

        self.size_hint_override = QSize(self.size_hint_override.width(),
                                        self.size_hint_override.height() + 10)
        self.sizeHintChanged.emit(self.index)
    def size_hint_dec(self):
        if not hasattr(self, 'size_hint_override'):
            self.size_hint_override = super().sizeHint()

        self.size_hint_override = QSize(self.size_hint_override.width(),
                                        self.size_hint_override.height() - 10)
        self.sizeHintChanged.emit(self.index)

    def sizeHint(self):
        if not hasattr(self, 'size_hint_override'):
            return super().sizeHint()
        else:
            return self.size_hint_override

    @pyqtSlot()
    def updatePreview(self):
        formula = self.input_box.toPlainText()
        self.mj_renderer.updatePreview(formula)

    @pyqtSlot()
    def on_commit_formula_button_clicked(self):
        # maybe trigger commit & close instead
        #self.prepareFormulaData()
        self.editingFinished.emit()

    @pyqtSlot()
    def on_discard_button_clicked(self):
        self.editingAborted.emit()

