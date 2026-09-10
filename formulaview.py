import logging, sys, os
from functools import partial
from enum import Enum, StrEnum
from PyQt6.QtWidgets import (QAbstractItemDelegate, QListView,
                             QSizePolicy, QAbstractItemView, QListWidgetItem, QStyle,
                             QStyledItemDelegate, QWidget, QLineEdit, QApplication, QLabel)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import (pyqtSignal, pyqtSlot, QAbstractItemModel, QDir, QEvent, QEventLoop, Qt, QTimer,
                          QMimeData, QMutex, QMutexLocker, QObject, QPoint, QRectF, QSettings,
                          QSize, QTemporaryFile, QUrl, QWaitCondition, QPersistentModelIndex,
                          QModelIndex)
from PyQt6.QtGui import (QPalette, QImage, QPainter, QColor, QStandardItem, QStandardItemModel,
                         QAction, QActionGroup, QPixmap)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtSvgWidgets import QSvgWidget
from mjrender import javascript_v3_extract, mj_enqueue, gen_render_html, MathJaxRenderer
from mjparse import gen_bracket_match_map, tokenize
from svgwebdisplay import SvgPixmapRasterizer

from texsyntax import MathJaxHighlighter

import matplotlib.pyplot as plt
plt.rc('mathtext', fontset='cm')

from menubuilder import build_menu, disable_unused_submenus
from collections import namedtuple

from io import BytesIO

# Move this to a modular debugging kit for PyQT.  Is there anything prebuilt that does this?
event_dict = {getattr(QEvent.Type, v): v for v in dir(QEvent.Type) if not v.startswith('_')}

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
        self.clipboard = QApplication.clipboard()

        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setUniformItemSizes(False)
        self.setSpacing(1)

        self.setViewMode(QListView.ViewMode.ListMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
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

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.listContextMenuRequested)
        self.delegate = FormulaDelegate(self)
        self.setItemDelegate(self.delegate)
        self.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setAcceptDrops(True)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

        self.mj_renderer = MathJaxRenderer(self)
        self.mj_renderer.formulaProcessed.connect(self.append_formula_svg)
        # Shared Chromium rasterizer for accurate list-item painting (one view, many pixmaps)
        self.svg_rasterizer = SvgPixmapRasterizer(parent=self, cache_size=96)
        self.svg_rasterizer.pixmapReady.connect(self._on_svg_pixmap_ready)
        self.installEventFilter(self)

    @pyqtSlot(bytes, QSize, float)
    def _on_svg_pixmap_ready(self, svg_bytes: bytes, logical_size: QSize, dpr: float):
        # Any row using this SVG can now paint the cached pixmap
        self.viewport().update()


    def eventFilter(self, object: QObject, event: QEvent) -> bool:
        ...

        if event.type() == QEvent.Type.KeyPress:  # and obj is self:

            if event.key() == Qt.Key.Key_Delete and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                for index in self.selectedIndexes():
                    self.deleteEquation(index.row())

                return True

        return False

    def closeEditor(self, editor: QWidget, hint: QAbstractItemDelegate.EndEditHint) -> None:
        if not getattr(editor, 'delegate_processed', False):
            # Mark so we do not re-enter, then let the normal close proceed.
            # Emitting editingAborted is enough for our abort path; we must still
            # call super so the view finishes removing the editor.
            editor.delegate_processed = True
            try:
                editor.editingAborted.emit()
            except Exception:
                pass
            import traceback
            logging.debug('closeEditor: aborting (Qt-initiated close)')
            logging.debug('closeEditor stack:\n%s', ''.join(traceback.format_stack()))
        return super().closeEditor(editor, hint)

    def append_new_and_edit(self):
        win = self.window()
        logging.debug('BEFORE add: win_id=%s geo=%s visible=%s',
                      id(win), win.geometry(), win.isVisible())
        index:QModelIndex = self.append_new()
        self.setCurrentIndex(index)
        ok = self.edit(index)
        logging.debug('append_new_and_edit: edit() returned %s, state=%s', ok, self.state())
        logging.debug('AFTER  add: win_id=%s geo=%s visible=%s state=%s',
                      id(win), win.geometry(), win.isVisible(), self.state())

    def append_new(self):
        item = QStandardItem()
        item.setFlags(Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled |
                      Qt.ItemFlag.ItemIsDragEnabled)
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

        selection = menu.exec(self.mapToGlobal(pos))
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
        rec = item.data(Qt.ItemDataRole.UserRole)
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
        rec = item.data(Qt.ItemDataRole.UserRole)
        svg = rec.svg_data
        QApplication.clipboard().setText(svg.decode())


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
        rec = item.data(Qt.ItemDataRole.UserRole)
        svg = rec.svg_data

        renderer = QSvgRenderer()
        renderer.load(svg.replace(b'currentColor', b'black'))
        image = QImage(renderer.defaultSize() / rfactor, QImage.Format.Format_ARGB32)
        #image = QImage(renderer.defaultSize() / rfactor, QImage.Format.Format_RGB666)
        #image.fill(0x00000000)  # fill the image with transparent pixels
        image.fill(Qt.GlobalColor.white)
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
        QApplication.clipboard().setMimeData(data)


    @register
    def copyEquation(self, row):

        item = self.model().item(row)
        formula = item.text()
        QApplication.clipboard().setText(formula)
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
        svg.renderer().setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        # svg.sizeHint() returns (460, 345)
        self.layout().addWidget(svg)

    def append_formula_svg(self, formula, svg: bytes):
        item = QStandardItem()
        item.setFlags(
            Qt.ItemFlag.ItemIsEditable
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsDragEnabled
        )
        item.setText(formula)
        item.setData(FormulaData(svg, None), Qt.ItemDataRole.UserRole)
        self.model().appendRow([item])
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
                f.write(r'\[' + formula + r'\]\n')

    def load_from_text(self, filename):
        with open(filename, 'rt') as f:
            formula_list = f.read().split(r'\]\n\[')
            if len(formula_list) > 0:
                formula_list[0] = formula_list[0].removeprefix(r'\[')
                formula_list[-1] = formula_list[-1].removesuffix(r'\]\n')
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
        if option.state & QStyle.StateFlag.State_Editing:
            print('paint: called, State_Editing')

        rec = index.data(Qt.ItemDataRole.UserRole)
        if rec is not None and rec.svg_data is not None:
            svg = rec.svg_data
            if option.state & QStyle.StateFlag.State_Selected:
                bg_color = option.palette.highlight().color()
            else:
                bg_color = option.palette.color(
                    QPalette.ColorGroup.Active, QPalette.ColorRole.Base
                )
            painter.fillRect(QRectF(option.rect), bg_color)

            parent = self.parent()
            ras = getattr(parent, "svg_rasterizer", None)
            rect = option.rect
            logical = QSize(max(rect.width(), 1), max(rect.height(), 1))
            dpr = painter.device().devicePixelRatioF() if painter.device() else 1.0

            pm = None
            if ras is not None:
                pm = ras.get(svg, logical, dpr)

            painter.save()
            if pm is not None and not pm.isNull():
                # Chromium-accurate pixmap (may arrive async on first paint)
                target = QRectF(rect)
                # Center if pixmap aspect differs slightly from cell
                dpr_pm = pm.devicePixelRatio() or 1.0
                pm_logical = QSize(
                    max(1, int(pm.width() / dpr_pm)),
                    max(1, int(pm.height() / dpr_pm)),
                )
                scaled = pm_logical.scaled(logical, Qt.AspectRatioMode.KeepAspectRatio)
                x = rect.x() + (rect.width() - scaled.width()) / 2
                y = rect.y() + (rect.height() - scaled.height()) / 2
                target = QRectF(x, y, scaled.width(), scaled.height())
                painter.drawPixmap(target.toRect(), pm)
            else:
                # Cache miss or no rasterizer: brief QSvg fallback (may show the
                # known overline artifacts until Chromium pixmap arrives).
                draw_color = option.palette.color(
                    QPalette.ColorGroup.Active, QPalette.ColorRole.Text
                )
                if option.state & QStyle.StateFlag.State_Selected:
                    draw_color = option.palette.color(
                        QPalette.ColorGroup.Active,
                        QPalette.ColorRole.HighlightedText,
                    )
                self.renderer.load(
                    svg.replace(b"rgb(0%, 0%, 0%)", draw_color.name().encode())
                )
                self.renderer.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
                self.renderer.render(painter, QRectF(rect))
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
        # QStyle.StateFlag.State_Editing flag set the way I expected it.
        self.initStyleOption(option, index)
        base_hint = super().sizeHint(option, index)
        viewport_hint = self.parent().maximumViewportSize()

        rec = index.data(Qt.ItemDataRole.UserRole)
        parent:FormulaView = self.parent()
        pindex = QPersistentModelIndex(index)

        # if parent.state() == QAbstractItemView.State.EditingState:

        # if option.state & QStyle.StateFlag.State_Editing: # <- this does not properly detect an item edit
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
            self.renderer.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)

            vpad = settings.value("display/verticalPadding", 200, type=int)
            rfactor = settings.value("display/reductionFactor", 24, type=float)

            ####self.renderer.setViewBox(self.renderer.viewBox().adjusted(0, -vpad, 0, vpad))

            if self.renderer.isValid():
                logging.debug('delegate: basing size on renderer')
                hint = self.renderer.defaultSize() * 4
                # Guard against degenerate / empty SVGs (MathJax empty formula)
                if not hint.isValid() or hint.width() <= 0 or hint.height() <= 0:
                    logging.debug('delegate: invalid/empty SVG size, falling back')
                    hint = QSize(400, 80)
                else:
                    if hint.width() > viewport_hint.width() > 0:
                        hint = hint * (viewport_hint.width() / hint.width())
                    # never return a zero-height row
                    if hint.height() < 40:
                        hint.setHeight(40)
            else:
                hint = QStyledItemDelegate.sizeHint(self, option, index)
                if not hint.isValid() or hint.height() < 1:
                    hint = QSize(400, 80)

            data = index.data()
            logging.debug('delegate: rfactor=%s vpad=%s formula=%r sizeHint=%s',
                          rfactor, vpad, data, hint)
            return hint
        else:
            try:
                editor = self.get_editor_from_index(index)
                hint = editor.sizeHint()
                return hint
            except:
                # First insertion of an empty item — use a modest default so the
                # main window does not jump dramatically.
                hint = QSize(400, 120)
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
        #if not option.state & QStyle.StateFlag.State_Editing:

        model = index.model()
        # Build the editor unparented so setupUi's QWebEngineView is NOT
        # inserted into the already-visible main window (that causes
        # withdraw/show on Linux). Parent it to the view only after init.
        editor = FormulaEdit(None)
        editor.setParent(parent)
        self.associate_editor_index(editor, index)
        editor.editingFinished.connect(self.commit_and_close_editor)
        editor.editingAborted.connect(self.abort_and_close_editor)
        pindex = QPersistentModelIndex(index)

        def emitSizeHintChanged():
            # print('emitSizeChanged:')
            index = pindex.model().index(pindex.row(), pindex.column(), pindex.parent())
            self.sizeHintChanged.emit(index)

        editor.sizeHintChanged.connect(emitSizeHintChanged)
        editor.updateIndexThing(QPersistentModelIndex(index))
        # Do NOT emit sizeHintChanged here — it races with the editor being
        # installed and can cause Qt to cancel the edit. The editor will emit
        # sizeHintChanged itself once it is ready / when text changes.
        # NOTE: do NOT emit model.layoutChanged here either.
        self.parent().scrollTo(index)
        return editor

    def setEditorData(self, editor, index):
        """ Sets the data to be displayed and edited by our custom editor. """
        self.editing_index = QPersistentModelIndex(index)

        editor.updateIndexThing(self.editing_index)

        if index:
            formula = index.data() or ''
            # Block signals so setPlainText does not fire textChanged → sizeHintChanged
            # during the critical install window.
            editor.input_box.blockSignals(True)
            editor.input_box.setPlainText(formula)
            editor.input_box.blockSignals(False)
        else:
            super().setEditorData(editor, index)


    def setModelData(self, editor, model, index):
        """ Get the data from our custom editor and stuffs it into the model. """

        editor.prepareFormulaData()
        formula, svg_data = editor.getFormulaData()

        rec = FormulaData(svg_data, None)

        model.setData(index, editor.formula)
        model.setData(index, rec, Qt.ItemDataRole.UserRole)


    @pyqtSlot()
    def abort_and_close_editor(self):
        editor = self.sender()
        editor.delegate_processed = True
        self.closeEditor.emit(editor, QAbstractItemDelegate.EndEditHint.NoHint)

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
            self.closeEditor.emit(editor, QAbstractItemDelegate.EndEditHint.EditNextItem)
        else:
            self.commitData.emit(editor)
            self.closeEditor.emit(editor, QAbstractItemDelegate.EndEditHint.NoHint)

    #def editorEvent(self, event: QtCore.QEvent, model: QtCore.QAbstractItemModel, option: 'QStyleOptionViewItem', index: QtCore.QModelIndex) -> bool:

    #def closeEditor(self, editor: QWidget, hint: QAbstractItemDelegate.EndEditHint) -> None:
    #@pyqtSlot(QWidget, QAbstractItemDelegate.EndEditHint)
    def close_editor(self, editor:QWidget, hint=QAbstractItemDelegate.EndEditHint.NoHint) -> None:
        #shouldn't need to do this again I think
        #self.closeEditor.emit(editor, QAbstractItemDelegate.EndEditHint.NoHint)
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

            # NOTE: do NOT emit model.layoutChanged here — it causes visual glitches / editor abort
        else:
            import traceback
            logging.debug('close_editor: index is none (association already cleared)')
            logging.debug('close_editor stack:\n%s', ''.join(traceback.format_stack()))

    def updateEditorGeometry(self, editor, option, index:QModelIndex):
        rect = option.rect;
        sizeHint = editor.sizeHint();
        if (rect.height() < sizeHint.height()):
            rect.setHeight(sizeHint.height())

        editor.setGeometry(rect)

    def eventFilter(self, editor, event: QEvent):
        # Log anything that might close the editor so we can see the real trigger.
        et = event.type()

        if et == QEvent.Type.LayoutRequest:
            pindex = self.get_index_from_editor(editor)
            if pindex is not None and pindex.isValid():
                index = pindex.model().index(pindex.row(), pindex.column(), pindex.parent())
                self.sizeHintChanged.emit(index)
            return False  # do not consume

        if et == QEvent.Type.KeyPress:
            key = event.key()
            logging.debug('delegate eventFilter KeyPress key=%s modifiers=%s',
                          key, event.modifiers())
            # Do NOT close the editor from the delegate on Escape.
            # FormulaEdit.eventFilter already handles Ctrl+Enter / Escape.
            # Emitting closeEditor here was the source of the instant abort.
            if key == Qt.Key.Key_Escape:
                logging.debug('delegate eventFilter: Escape seen — letting default handle it')
                # Fall through to super(); do not emit closeEditor ourselves.
                pass

        if et in {QEvent.Type.FocusAboutToChange, QEvent.Type.FocusOut}:
            new_focus = QApplication.focusWidget()
            logging.debug('delegate eventFilter focus event=%s new_focus=%s editor=%s',
                          et, new_focus, editor)
            # Never auto-close on focus loss. Opening an inline editor often
            # produces a FocusOut with new_focus=None (focus flicker from the
            # button click / view). Closing is only done via Escape, Ctrl+Enter,
            # or the commit/discard buttons on FormulaEdit.
            return True

        return super().eventFilter(editor, event)


from ui_loader import load_ui_class, UI_CLASSES

Ui_settings = load_ui_class(*UI_CLASSES['Settings'])
Ui_FormulaEdit = load_ui_class(*UI_CLASSES['FormulaEdit'])

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
        # formulaProcessed is connected in _init_renderer after the page exists
        self.waitPreview = QMutex()
        self.previewUpdated = QWaitCondition()
        self.loop = QEventLoop(QApplication.instance())
        self.highlight = MathJaxHighlighter(self.input_box.document())
        # installing event filter on QPlainTextEdit seems to override Ctrl+Enter default behavior
        self.input_box.installEventFilter(self)
        # self.installEventFilter(self)
        self.input_box.textChanged.connect(lambda: self.sizeHintChanged.emit(self.index))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        bg_color = self.palette().color(QPalette.ColorGroup.Active, QPalette.ColorRole.Base)
        self.setStyleSheet(f"background-color: {bg_color.name()}")
        self.input_box.cursorPositionChanged.connect(self.cursor_position_changed)
        self.cursor_position_changed()

    def initUI(self):
        self.setupUi(self)
        self.mj_renderer = None
        self._web_preview_ready = False
        # Do NOT call setFocus here — the editor is still being constructed.
        # Focus is taken in showEvent once the editor is visible.
        self.setAutoFillBackground(True)

        # Critical: setupUi creates a QWebEngineView named "preview" and parents it
        # into this editor, which is already under the visible main window.
        # Embedding the first (or a new) QWebEngineView into a mapped top-level
        # window causes some Linux compositors to withdraw+show the window.
        # Replace it with a plain placeholder now; create the real view later.
        self._replace_preview_with_placeholder()

    @staticmethod
    def _find_layout_index(widget):
        """Return (layout, index) for *widget* in its parent layout tree.

        parent.layout() is the *top-level* layout on the parent widget. The
        preview lives in the nested verticalLayout, so indexOf(preview) on the
        outer layout is -1 and a naive addWidget() appends below the whole
        editor block (preview ends up under the input box).
        """
        if widget is None:
            return None, -1
        parent = widget.parentWidget()
        if parent is None or parent.layout() is None:
            return None, -1

        def search(layout):
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item is None:
                    continue
                if item.widget() is widget:
                    return layout, i
                child = item.layout()
                if child is not None:
                    found = search(child)
                    if found[0] is not None:
                        return found
            return None, -1

        return search(parent.layout())

    def _replace_preview_with_placeholder(self):
        old = getattr(self, 'preview', None)
        if old is None:
            return
        logging.debug('FormulaEdit: replacing preview type=%s with placeholder',
                      type(old).__name__)
        parent = old.parentWidget() or self
        layout, idx = self._find_layout_index(old)
        placeholder = QLabel(parent)
        placeholder.setObjectName('preview_placeholder')
        placeholder.setMinimumHeight(old.minimumHeight() if old.minimumHeight() > 0 else 200)
        placeholder.setSizePolicy(old.sizePolicy())
        placeholder.setText('(preview loading…)')
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if layout is not None and idx >= 0:
            layout.removeWidget(old)
            layout.insertWidget(idx, placeholder)
        elif layout is not None:
            layout.insertWidget(0, placeholder)  # designed order: preview above input
        else:
            logging.warning('FormulaEdit: no layout found for preview; order may be wrong')
        old.setParent(None)
        old.deleteLater()
        self.preview = placeholder

    def _promote_preview_to_webengine(self):
        """Install a real QWebEngineView in the editor for live MathJax preview.

        Safe only *after* the main window has already embedded a QWebEngineView
        (startup warm-up). The first embed remaps the window surface; later
        embeds do not.
        """
        if self._web_preview_ready:
            return
        if isinstance(getattr(self, 'preview', None), QWebEngineView):
            self._web_preview_ready = True
            return

        placeholder = getattr(self, 'preview', None)
        parent = placeholder.parentWidget() if placeholder is not None else self
        layout, idx = self._find_layout_index(placeholder)
        view = QWebEngineView(parent)
        view.setObjectName('preview')
        if placeholder is not None:
            mh = placeholder.minimumHeight()
            view.setMinimumHeight(mh if mh > 0 else 200)
            view.setSizePolicy(placeholder.sizePolicy())
        else:
            view.setMinimumHeight(200)
        if layout is not None and idx >= 0:
            layout.removeWidget(placeholder)
            layout.insertWidget(idx, view)
        elif layout is not None:
            layout.insertWidget(0, view)  # preview above input (matches .ui)
        else:
            logging.warning('FormulaEdit: no layout found when promoting preview')
        if placeholder is not None:
            placeholder.setParent(None)
            placeholder.deleteLater()
        self.preview = view
        self._web_preview_ready = True
        logging.debug('FormulaEdit: QWebEngineView preview installed (after warm-up)')

    def _init_renderer(self):
        if self.mj_renderer is not None:
            return

        main_win = self.window()
        warmup = getattr(main_win, '_webengine_warmup', None)
        if warmup is None:
            # Warm-up not done yet — try again shortly rather than embed first.
            logging.debug('FormulaEdit: warm-up missing, deferring renderer init')
            QTimer.singleShot(100, self._init_renderer)
            return

        if not self._web_preview_ready:
            self._promote_preview_to_webengine()

        self.mj_renderer = MathJaxRenderer(self)
        self.preview.setPage(self.mj_renderer)
        self.mj_renderer.formulaProcessed.connect(self.setFormulaData)
        formula = self.input_box.toPlainText()
        if formula:
            self.mj_renderer.updatePreview(formula)
        self.input_box.setFocus(Qt.FocusReason.OtherFocusReason)
        logging.debug('FormulaEdit: live MathJax preview attached')

    def showEvent(self, event):
        super().showEvent(event)
        self.input_box.setFocus(Qt.FocusReason.OtherFocusReason)
        # Defer WebEngine creation until after this event returns and the window
        # has finished mapping the editor. A short delay avoids the withdraw/show.
        if not self._web_preview_ready:
            QTimer.singleShot(50, self._init_renderer)

    def cursor_position_changed(self):
        # i think we should call rehighlight[Block] here
        self.highlight.update_cursor(self.input_box.textCursor())

    def updateIndexThing(self, index):
        self.index = index
        # Do not emit sizeHintChanged here — during createEditor/setEditorData
        # that emission races with editor install and can cancel the edit.

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
        if self.mj_renderer is None:
            # Renderer not ready yet (should be rare); just take the text
            self.formula = self.input_box.toPlainText()
            self.svg_data = b''
            return
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

        if event.type() == QEvent.Type.KeyPress: # and obj is self:

            if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
                if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                    self.editingFinished.emit()
                    return True
                elif event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    return True
            elif event.key() == Qt.Key.Key_Escape:
                # maybe just send a signal or sth to remove the item, and that it was abandoned
                # self.closeEditor.emit() # method of delegate
                return False
            # elif event.key() == Qt.Key.Key_U:
            #     self.size_hint_inc()
            #     return False
            # elif event.key() == Qt.Key.Key_D:
            #     self.size_hint_dec()
            #     return False

        # elif event.type() == QEvent.Type.FocusOut:  # must be some other event
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
        if self.mj_renderer is None:
            return
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

