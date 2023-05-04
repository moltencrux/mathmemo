#import sys
#from functools import partial
#from PyQt5.QtWidgets import *
#from PyQt5.QtCore import Qt, QUrl, QEvent, QSize, QItemSelection, QItemSelectionModel, QMimeData, pyqtSlot
from PyQt5.QtCore import QObject, QSettings, QUrl, pyqtProperty, pyqtSignal, pyqtSlot
#from PyQt5.QtGui import QTextDocument, QPalette, QColor, QCursor, QClipboard, QImage, QPainter
from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineView, QWebEngineSettings
from PyQt5.QtWebChannel import QWebChannel
#from PyQt5.QtSvg import QSvgWidget, QGraphicsSvgItem, QSvgRenderer
#from io import BytesIO
#from texsyntax import LatexHighlighter
import matplotlib.pyplot as plt
from time import perf_counter
#
#from PyQt5.QtWidgets import (QWidget, QSlider, QLineEdit, QLabel, QPushButton, QScrollArea,QApplication,
#                             QHBoxLayout, QVBoxLayout, QMainWindow, QSizePolicy, QAbstractItemView)
#
#from PyQt5 import QtWidgets, uic
#
#from formulalist import FormulaList
#
#from pysvg.parser import parse

# from PyQt5 import Qt
# 'PyQt5.QtWebEngineWidgets.QWebEngineSettings.ShowScrollBars'

settings = QSettings()


context = r'''\newcommand{\Ex}{\mathop{\rm Ex}}
               \newcommand{\T}{\mathop{\rm T}}
               \newcommand{\range}{\mathop{\rm range}}
           '''.replace('{', '{{').replace('}', '}}')


mathjax_v2_url = "file:///usr/share/javascript/mathjax/MathJax.js?delayStartupUntil=onload"

mathjax_v3_url_remote = "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js?delayStartupUntil=onload"

mathjax_v3_url = 'file:///usr/share/javascript/mathjax@3/es5/tex-svg-full.js'

mathjax_config_old = r"""
      MathJax.Hub.Config({
        showMathMenu: false,
        jax: ['input/TeX', 'output/SVG'],
        extensions: ['tex2jax.js', 'MathMenu.js', 'MathZoom.js'],
        TeX: {
          extensions: ['AMSmath.js', 'AMSsymbols.js', 'noErrors.js', 'noUndefined.js']
        }
      });
""".replace('{', '{{').replace('}', '}}')

mathjax_config_v2_old = r"""
      MathJax.Hub.Config({
        showMathMenu: false,
        jax: ['input/TeX', 'output/SVG'],
        extensions: ['tex2jax.js', 'MathMenu.js', 'MathZoom.js'],
        TeX: {
          extensions: ['AMSmath.js', 'AMSsymbols.js', 'noErrors.js', 'noUndefined.js']
        }
      });
""".replace('{', '{{').replace('}', '}}')

mathjax_v2_config_badq = r"""
    <script type="text/x-mathjax-config">
      MathJax.Hub.Config({
        jax: ["input/TeX","input/MathML","input/AsciiMath","output/SVG"],
        extensions: ["tex2jax.js","mml2jax.js","asciimath2jax.js","MathMenu.js",
                     "MathZoom.js","AssistiveMML.js", "a11y/accessibility-menu.js"],
        TeX: { extensions:
          ["AMSmath.js","AMSsymbols.js","noErrors.js","noUndefined.js"]
      });
    </script>
""".replace('{', '{{').replace('}', '}}')

mathjax_v2_config_kinda_ok = r"""
<script type="text/x-mathjax-config">
  MathJax.Hub.Config({
    extensions: ["tex2jax.js"],
    jax: ["input/TeX", "output/HTML-CSS"],
    tex2jax: {
      inlineMath: [ ['$','$'], ["\\(","\\)"] ],
      displayMath: [ ['$$','$$'], ["\\[","\\]"] ],
      processEscapes: true
    },
    "HTML-CSS": { fonts: ["TeX"] }
  });
</script>
""".replace('{', '{{').replace('}', '}}')

mathjax_v2_config = r"""
<script type="text/x-mathjax-config">
  MathJax.Hub.Config({
    extensions: ["tex2jax.js"],
    jax: ["input/TeX","input/MathML","input/AsciiMath","output/SVG"],
    tex2jax: {
      inlineMath: [ ['$','$'], ["\\(","\\)"] ],
      displayMath: [ ['$$','$$'], ["\\[","\\]"] ],
      processEscapes: true
    },
    TeX: {
      extensions: ['AMSmath.js', 'AMSsymbols.js', 'noErrors.js', 'noUndefined.js']
    },
    SVG: {
      //useFontCache: false,
      useGlobalCache: false
    }
  });
</script>
"""

mathjax_v2_config_test1 = r"""
<script type="text/x-mathjax-config">
MathJax.Hub.Config({
    extensions: ["tex2jax.js"],
    extensions: ["tex2jax.js","MathEvents.js","MathZoom.js","MathMenu.js","toMathML.js","TeX/noErrors.js","TeX/noUndefined.js","TeX/AMSmath.js","TeX/AMSsymbols.js","fast-preview.js","AssistiveMML.js","[a11y]/accessibility-menu.js"],
    jax: ["input/TeX","output/SVG","output/PreviewHTML"]
});

MathJax.Ajax.loadComplete("[MathJax]/config/TeX-AMS_SVG-full.js");
</script>
""".replace('{', '{{').replace('}', '}}')

mathjax_config_orig_working = r"""
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

mathjax_config_orig = r"""
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

page_template_orig = r"""
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
      <mathjax id="mathjax-context" style="font-size:2.3em">\[{context}\]</mathjax> <mathjax id="mathjax-container" style="font-size:2.3em">\[{{formula}}\]</mathjax>
    </div>
  </body>
</html>
"""

'''
  chtml: {
    displayIndent: "2em"
  },
  options: {
    ignoreHtmlClass: 'tex2jax_ignore',
    processHtmlClass: 'tex2jax_process'
  }
'''

mathjax_v3_config = r"""
<script type="text/javascript">
  window.MathJax = {
    options: {
        enableMenu: false, ignoreHtmlClass:
            'tex2jax_ignore', processHtmlClass:
            'tex2jax_process' },
    chtml: {
        displayIndent: "2em"
    },
    loader: { load: ['input/tex-base', 'output/svg', 'ui/menu', '[tex]/require', '[tex]/noerrors', '[tex]/mathtools']
    },
    tex: {packages: {'[+]': ['noerrors', 'ams', 'noundefined', 'mathtools']},
      macros: {
        RR: "{\\\\bf R}",
        bold: ["{\\\\bf #1}", 1]
      }
    },
    
    startup: {
      ready: () => {
        MathJax.startup.defaultReady();
        MathJax.startup.promise.then(() => {
          var math = document.getElementById("rescale");
          var w = math.offsetWidth, W = math.parentNode.offsetWidth;
          if (w > W) {
            math.style.fontSize = (100*W/w)+"%";
          MathJax.startup.document.getMathItemsWithin(math)[0].Rerender();
        }
        console.log('MathJax initial typesetting complete');
        });
      }
    }
  };
</script>
"""

#.replace('{', '{{').replace('}', '}}')

qchannel_js = r"""
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script type="text/javascript">
    'use strict';

    var placeholder = document.getElementById('placeholder');

    var updateText = function (text) {
        placeholder.innerHTML = text;
        console.log(text);
    }

    new QWebChannel(qt.webChannelTransport,
        function (channel) {
            var handler = channel.objects.handler;
            window.handler = handler;
            updateText(handler.text);
            handler.textChanged.connect(updateText);
        }
    );
</script>
""".replace('{', '{{').replace('}', '}}')

mj_enqueue = r"""
    // MathJax.Hub.Queue(["Typeset", MathJax.Hub]);
    MathJax.Hub.Queue(function() {
        svgOutput = document.getElementById('mathjax-container').getElementsByTagName('svg')[0].outerHTML;
        window.handler.sendSvg(svgOutput);
        console.error('queue processed');
    });
"""


page_template = r"""
<head>
<div id="placeholder"></div>
<style>.box {{{{
  width : 100%
  margin: 0 auto 0 auto;
  border: 1px solid black;
  padding: 0 0 0 0 ;
  text-align: center;
}}}}</style>
</head>

<body>  

{qchannel}

{mj_config}
  
<script type="text/javascript" src="{url}"></script>

<mathjax id="mathjax-context" style="font-size:2.3em">\[{context}\]</mathjax>
<div class="box"><div id="rescale" style="display:inline-block">
<mathjax id="mathjax-container" style="font-size:2.3em">\[{{formula}}\]</mathjax>
</div></div>
</body>
"""

    # .format(url=mathjax_url, config=mathjax_config, context=context)

javascript_v3_extract = r'''
var mjelement = document.getElementById('mathjax-container');
mjelement.getElementsByTagName('svg')[0].outerHTML;
'''
javascript_v2_extract = r'''
(function( window, document, undefined ) {
  document.getElementsByTagName('svg')[0].outerHTML;
}( window, window.document ));
'''

javascript_v2_extract_ = r'''
    MathJax.Hub.Queue(["Typeset", MathJax.Hub]);
    MathJax.Hub.Queue(function() {
        let svgOutput = document.getElementsByTagName('svg')[0].outerHTML;
        window.pyqt_output = VsvgOutput;
    });
'''

mathjax_v2_config_test = """
<script type="text/x-mathjax-config">
    MathJax.Hub.Config({
        extensions: ["tex2jax.js"],
        extensions: ["tex2jax.js","MathEvents.js","MathZoom.js","MathMenu.js","toMathML.js","TeX/noErrors.js","TeX/noUndefined.js","TeX/AMSmath.js","TeX/AMSsymbols.js","fast-preview.js","AssistiveMML.js","[a11y]/accessibility-menu.js"],
        jax: ["input/TeX","output/SVG","output/PreviewHTML"],
	SVG: {
	    useGlobalCache: false,
        },
    });
    MathJax.Ajax.loadComplete("[MathJax]/config/TeX-AMS_SVG-full.js");
</script>
"""
mathjax_v2_config_test = """
<script type="text/x-mathjax-config">
</script>
"""

mj_v3_scripts = r"""
<script type="text/javascript">
    'use strict';
    
    function typeset(code) {
        MathJax.startup.promise = MathJax.startup.promise
        .then(() => MathJax.typesetPromise(code()))
        .catch((err) => console.error('Typeset failed: ' + err.message));
        return MathJax.startup.promise;
    };

    var updatePreview = function (formula) {
        typeset(() => {
            console.error('updatePreview called: ' + formula);
            const math = document.querySelector('#mathjax-container');
            math.innerHTML = '\\[' + formula + '\\]';
            return [math];
        });
    }; 
    /*
    var updateText = function (text) {
        var math = MathJax.tex2svg(text);  
        var math_svg = math.getElementsByTagName('svg')[0];
        console.error('updateText called: ' + text);
        console.error(typeof math_svg);
        console.error(math_svg);
        window.handler.sendSvg(text, math_svg.outerHTML);
    };
    */
    
    var submitFormula = function (formula) {
        var math = MathJax.tex2svg(formula);  
        var math_svg = math.getElementsByTagName('svg')[0];
        console.error('submitFormula called: ' + formula);
        console.error(typeof math_svg);
        console.error(math_svg);
        window.handler.sendSvg(formula, math_svg.outerHTML);
        console.error('submitFormula', Math.floor(Date.now() / 1000))
    };
    
    var updateText = submitFormula
    
    new QWebChannel(qt.webChannelTransport, function (channel) {
            var handler = channel.objects.handler;
            window.handler = handler;
            //updateText(handler.text);
            handler.textChanged.connect(updateText);
            handler.formulaChanged.connect(updatePreview);
            handler.formulaSubmitted.connect(submitFormula);
        }
    );

</script>
"""

mj_v2_scripts = """
<script type="text/javascript">
    'use strict';
    //was a separate script, but seems unnecessary, so commenting out for now
    //MathJax.Hub.Queue(["Typeset", MathJax.Hub]);
    
    var updatePreview = function (formula) {
        console.error('updatePreview:  queueing updates: ' + formula);
        console.error('updatePreview', Math.floor(Date.now() / 1000))
        console.error(formula);
        MathJax.Hub.Queue(["Text", window.eq_jax, formula]);
        
        //MathJax.Hub.Queue(["Text", window.eq_jax, formula, updateSvg]);
        //window.mj_container.value = formula;
        //MathJax.Hub.Queue(["Typeset", MathJax.Hub, "mathjax-container"]);
        //MathJax.Hub.Queue(updateSvg);
        //MathJax.Hub.Queue(["Text", eq_jax, formula]);
        //MathJax.Hub.Queue(["Typeset", MathJax.Hub, "mathjax-container"]);
        //MathJax.Hub.Queue(["Typeset", MathJax.Hub, mj_container]);
        //eq_jax.Text(formula, updateSvg);

        //mj_container.innerHTML = formula;

        //console.error('JS: updateText: ' + formula);
        //updateSvg();
    };
    
    var submitFormula = function (formula) {
        console.error('submitFormula', Math.floor(Date.now() / 1000))
        console.error('submitFormula: queueing updates: ' + formula);
        console.error(formula);
        //MathJax.Hub.Queue(function () {
        //    window.eq_jax.style.visibility = "visible";
        //});
        MathJax.Hub.Queue(["Text", window.eq_jax, formula, [updateSvg, formula]]);
        
            
        //MathJax.Hub.Queue(["Text", window.eq_jax, formula]);
        
        //MathJax.Hub.Queue(["Text", window.eq_jax, formula, updateSvg]);
        //window.mj_container.value = formula;
        //MathJax.Hub.Queue(["Typeset", MathJax.Hub, "mathjax-container"]);
        //MathJax.Hub.Queue(updateSvg);
        //MathJax.Hub.Queue(["Text", eq_jax, formula]);
        //MathJax.Hub.Queue(["Typeset", MathJax.Hub, "mathjax-container"]);
        //MathJax.Hub.Queue(["Typeset", MathJax.Hub, mj_container]);
        //eq_jax.Text(formula, updateSvg);

        //mj_container.innerHTML = formula;

        //console.error('JS: updateText: ' + formula);
        //updateSvg();
    };
    
    function updateSvg (formula) {
        console.error('updateSvg', Math.floor(Date.now() / 1000))
        const math = document.querySelector('#mathjax-container');
        var math_svg = math.getElementsByTagName('svg')[0];
        console.error('JS updateSvg: ' + math)
        console.error('JS updateSvg: ' + math_svg)
        
        var svgOutput;
        try {
            svgOutput = window.mj_container.getElementsByTagName('svg')[0].outerHTML;
        }
        catch (err) {
            svgOutput = null;
        }

        //svgOutput = document.getElementsByTagName('svg')[0].outerHTML;
        //svgOutput = document.getElementById('mathjax-container').getElementsByTagName('svg')[0].outerHTML;
        //svgOutput = window.mj_container.innerHTML;
        if (math_svg != null) {
            console.error('JS update SVG, sending back')
            console.error(math_svg);
            console.error('formula: ' + formula);
            window.handler.sendSvg(formula, math_svg.outerHTML);
        }
    }
    
    MathJax.Hub.Queue(function() {
        var mj_container = document.getElementById("mathjax-container");
        window.mj_container = mj_container;
        var eq_jax = MathJax.Hub.getAllJax("mathjax-container")[0];
        window.eq_jax = eq_jax;
        
        
        window.updateText = submitFormula 

        window.updateSvg = updateSvg

        new QWebChannel(qt.webChannelTransport, function (channel) {
                console.error('new QWebChannel')
                var handler = channel.objects.handler;
                window.handler = handler;
                //updateText(handler.text);
                //updatePreview(handler.formula);
                //handler.textChanged.connect(updatePreview);
                handler.formulaChanged.connect(updatePreview);
                handler.formulaSubmitted.connect(submitFormula);
                console.error('registered submitFormula')
            }
        );

    });

</script>
"""

page_template = r"""
<!doctype html>
<html lang="en">
<meta charset="utf-8">
<head>
{mj_config}
<script type="text/javascript" src="{url}"></script>
<script type="text/javascript" src="qrc:///qtwebchannel/qwebchannel.js"></script>
</head>
<body>
<mathjax id="mathjax-container" style="font-size:2.3em">\[{formula}\]</mathjax>
</body>
{mj_scripts}
</html>
"""

plt.rc('mathtext', fontset='cm')
def gen_render_html():
    settings.sync()
    mathjax_version = settings.value('main/mathjaxVersion', '3', type=str)
    mathjax_default_url = ''
    mathjax_config = ''
    if mathjax_version == '3':
        mathjax_default_url = mathjax_v3_url
        html = page_template.format(mj_config=mathjax_v3_config, url=mathjax_default_url,
                                    mj_scripts=mj_v3_scripts, formula='{}')
    elif mathjax_version == '2':
        mathjax_default_url = mathjax_v2_url

        mathjax_url = settings.value("main/mathjaxUrl", mathjax_default_url, type=str)
        html = page_template.format(mj_config=mathjax_v2_config, url=mathjax_default_url,
                                 mj_scripts=mj_v2_scripts, formula='{}')
    with open('/tmp/tmp.pmIWl98k8x/mjv3dump.html', 'wt') as f:
        f.write(html)
    return html

# with open('generated.html', 'wt') as f:
#     f.write(gen_render_html())

# with open('old_working.html', 'wt') as f:
#     f.write(big_html)


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

class CallHandler(QObject):
    textChanged = pyqtSignal(str)
    formulaChanged = pyqtSignal(str)
    formulaSubmitted = pyqtSignal(str)
    svgChanged = pyqtSignal(str, bytes)

    def __init__(self):
        super().__init__()
        self._text = ''
        self._formula = ''

    def text(self):
        return self._text

    def formula(self):
        return self._formula

    def setText(self, text):
        self._text = text
        self.textChanged.emit(text)
        # print("emit textChanged")

    def setFormula(self, formula):
        self._formula = formula
        self.formulaChanged.emit(formula)
        # print("emit textChanged")

    def submitFormula(self, formula):
        self._formula = formula
        print('ZZ emitting formulaSubmitted: ', formula, perf_counter())
        self.formulaSubmitted.emit(formula)

    text = pyqtProperty(str, fget=text, fset=setText, notify=textChanged)
    formula = pyqtProperty(str, fget=formula, fset=setFormula, notify=formulaChanged)

    # I think the pyqtSlot decorateor lets you send a return value back to JS.
    # and JS can call any method on the registerd handler/channel.
    # @pyqtSlot(result=QVariant)
    # def test(self):
    #     print('XOXOXOXOXXXXOOXOOX: call received')
    #     return QVariant({"abc": "def", "ab": 22})

    @pyqtSlot(str, str)
    def sendSvg(self, formula, svg):
        # called by JS, receives items and sends signal to listener.
        svg_data = svg.encode()
        self.svg_data = svg_data
        self.formula = formula
        print('PY: sendSvg: ')
        print('PY:', formula)
        print('PY:', svg)
        print('PY: sending svgChanged signal: ', formula, perf_counter())
        self.svgChanged.emit(formula, svg_data)
        self.setFormula('')


    # take an argument from javascript - JS:  handler.test1('hello!')
    # @pyqtSlot(QVariant, result=QVariant)
    # def test1(self, args):
    #     print('i got')
    #     print(args)
    #     return "ok"

class MathJaxRenderer(QWebEnginePage):
    formulaProcessed = CallHandler.svgChanged

    def __init__(self):
        super().__init__()
        self._text = ""
        self.channel = QWebChannel()
        self.setWebChannel(self.channel)
        self.handler = CallHandler()
        # self.view = QWebEngineView()
        # self.view.setPage(self)
        self.channel.registerObject('handler', self.handler)
        self.setHtml(gen_render_html(), QUrl('file://'))
        self.loadFinished.connect(self._on_load_finished)
        self.handler.svgChanged.connect(self.formulaProcessed.emit)


    def _on_load_finished(self):
        # self.updatePreview('')
        xml_header = b'<?xml version="1.0" encoding="utf-8" standalone="no"?>'
        # self.runJavaScript("""
        #     var mjelement = document.getElementById('mathjax-container');
        #     mjelement.getElementsByTagName('svg')[0].outerHTML;
        # """, lambda result: self.update_svg(xml_header + result.encode()))

    def formula(self):
        return self._formula

    def submitFormula(self, formula):
        self.handler.submitFormula(formula)


    formula = pyqtProperty(str, fget=formula, fset=submitFormula, notify=formulaProcessed)

    # I think the pyqtSlot decorateor lets you send a return value back to JS.
    # and JS can call any method on the registerd handler/channel. WRONG.. not true
    # @pyqtSlot(result=QVariant)
    # def test(self):
    #     print('XOXOXOXOXXXXOOXOOX: call received')
    #     return QVariant({"abc": "def", "ab": 22})

    @pyqtSlot(str, str)
    def sendSvg(self, formula, svg):
        svg_data = svg.encode()
        self.svg_data = svg_data
        self.formula = formula
        print('PY: sendSvg: ')
        print('PY:', formula)
        print('PY:', svg)
        print('PY: sending svgChanged signal: ', formula, perf_counter())
        self.svgChanged.emit(formula, svg_data)



    # take an argument from javascript - JS:  handler.test1('hello!')
    # @pyqtSlot(QVariant, result=QVariant)
    # def test1(self, args):
    #     print('i got')
    #     print(args)
    #     return "ok"


    def append_content(self, content):
        # Append the formula to the list box
        content_html= f"{content}<br>"
        if '\\(' in content and '\\)' in content:
            # Use MathJax to render math expressions enclosed in \( and \)
            content_html = content_html.replace('\\(', '<mathjax style="font-size:2.3em" >').replace('\\)', '</mathjax>')
        # js_code = f"document.body.innerHTML += '{content_html}'; MathJax.typeset();"
        # self.text_area.page().runJavaScript(js_code)
        self.eq_list.append_formula(content)

    def updatePreview(self, formula):
        #self.handler.setText(formula)
        self.handler.setFormula(formula)
        #formula_str = self.input_box.toPlainText()
        #self.preview.setHtml(self.page_template.format(formula=formula_str), QUrl('file://'))

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


    def update_svg(self, svg:bytes):
        # add XML header
        formula = self.eq_queue.pop(0)
        self.eq_list.append_formula_svg(formula, svg)

