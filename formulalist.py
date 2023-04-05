#import sys

from PyQt5.QtWidgets import qApp, QListWidget, QLabel, QSizePolicy, QAbstractItemView, QListWidgetItem, QMenu
from PyQt5.QtCore import Qt, QSize, QMimeData
from PyQt5.QtGui import QPalette, QCursor, QImage, QPainter
from PyQt5.QtSvg import QSvgWidget, QSvgRenderer


class FormulaList(QListWidget):
    SvgRole = Qt.UserRole
    FormulaRole = Qt.UserRole + 1

    def __init__(self, parent=None, formulas=[]):
        super().__init__(parent)

        self.clipboard = qApp.clipboard()

        # self.setSizeAdjustPolicy(QListWidget.SizeAdjustPolicy.AdjustToContents)
        self.currentItemChanged.connect(lambda: print("QLW: Item Changed Signal"))
        self.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.setUniformItemSizes(False)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        # self.setStyleSheet("QListWidget:item { selection-background-color: red; }")
        # self.setStyleSheet("QListWidget::item:selected { background-color: red; }")
        self.setSpacing(1)

        self.setViewMode(QListWidget.ListMode)
        # self.formulas = []
        # self.images = []

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

        # Copy image to clipboard
        self.clipboard.setImage(image)
        print('copyImage called ', index)

    def copyEquation(self, index):

        item = self.item(index)
        formula = item.data(self.FormulaRole)

        app.clipboard().setText(formula)

        print('copyEquation called ', self.formula)

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


    def append_label(self, label):
        object = QLabel("TextLabel: " + label)
        self.layout().addWidget(object)
