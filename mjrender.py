#import sys
#from functools import partial
#from PyQt5.QtWidgets import *
#from PyQt5.QtCore import Qt, QUrl, QEvent, QSize, QItemSelection, QItemSelectionModel, QMimeData, pyqtSlot
from PyQt5.QtCore import QSettings
#from PyQt5.QtGui import QTextDocument, QPalette, QColor, QCursor, QClipboard, QImage, QPainter
from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineView, QWebEngineSettings
#from PyQt5.QtSvg import QSvgWidget, QGraphicsSvgItem, QSvgRenderer
#from io import BytesIO
#from texsyntax import LatexHighlighter
import matplotlib.pyplot as plt
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
mathjax_url = mathjax_v3_url

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
      useFontCache: false,
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
""".replace('{', '{{').replace('}', '}}')

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

big_html = r"""
<!doctype html>
<html lang="en">
<meta charset="utf-8">
<head>
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
<script type="text/javascript" src="file:///usr/share/javascript/mathjax/MathJax.js?delayStartupUntil=onload"></script>
<script>
    MathJax.Hub.Queue(["Typeset", MathJax.Hub]);
</script>
<script type="text/javascript" src="qrc:///qtwebchannel/qwebchannel.js"></script>
</head>
<body>
<mathjax id="mathjax-container" style="font-size:2.3em">$${x}$$</mathjax>
<script type="text/javascript">
    'use strict';

    MathJax.Hub.Queue(function() {
        var mj_container = document.getElementById("mathjax-container");
        if( mj_container == null) {
          console.error('mj_container is null');
        }
        window.mj_container = mj_container;
        var eq_jax = MathJax.Hub.getAllJax("mathjax-container")[0];
        window.eq_jax = eq_jax;
        
        var updateText = function (text) {
            console.error('queueing updates: ' + text);
            MathJax.Hub.Queue(["Text", window.eq_jax, text, [updateSvg, text]]);
            //MathJax.Hub.Queue(["Text", window.eq_jax, text, updateSvg]);
            //window.mj_container.value = text;
            //MathJax.Hub.Queue(["Typeset", MathJax.Hub, "mathjax-container"]);
            //MathJax.Hub.Queue(updateSvg);
            //MathJax.Hub.Queue(["Text", eq_jax, text]);
            //MathJax.Hub.Queue(["Typeset", MathJax.Hub, "mathjax-container"]);
            //MathJax.Hub.Queue(["Typeset", MathJax.Hub, mj_container]);
            //eq_jax.Text(text, updateSvg);
            
            //mj_container.innerHTML = text;
            
            //console.error('JS: updateText: ' + text);
            //updateSvg();
        };
        window.updateText = updateText
        
        function updateSvg () {
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
            if (svgOutput != null) {
                window.handler.sendSvg(svgOutput);
            }
        }
        window.updateSvg = updateSvg
        
        new QWebChannel(qt.webChannelTransport, function (channel) {
                var handler = channel.objects.handler;
                window.handler = handler;
                updateText(handler.text);
                handler.textChanged.connect(updateText);
            }
        );
        
    });
    
    
</script>
</body>
</html>
"""

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

mj_v2_scripts = """
<script type="text/javascript">
    'use strict';
    //was a separate script, but seems unnecessary, so commenting out for now
    //MathJax.Hub.Queue(["Typeset", MathJax.Hub]);
    
    MathJax.Hub.Queue(function() {
        var mj_container = document.getElementById("mathjax-container");
        if( mj_container == null) {
          console.error('mj_container is null');
        }
        window.mj_container = mj_container;
        var eq_jax = MathJax.Hub.getAllJax("mathjax-container")[0];
        window.eq_jax = eq_jax;

        var updateText = function (text) {
            console.error('queueing updates: ' + text);
            console.error(text);
            MathJax.Hub.Queue(["Text", window.eq_jax, text, [updateSvg, text]]);
            //MathJax.Hub.Queue(["Text", window.eq_jax, text, updateSvg]);
            //window.mj_container.value = text;
            //MathJax.Hub.Queue(["Typeset", MathJax.Hub, "mathjax-container"]);
            //MathJax.Hub.Queue(updateSvg);
            //MathJax.Hub.Queue(["Text", eq_jax, text]);
            //MathJax.Hub.Queue(["Typeset", MathJax.Hub, "mathjax-container"]);
            //MathJax.Hub.Queue(["Typeset", MathJax.Hub, mj_container]);
            //eq_jax.Text(text, updateSvg);

            //mj_container.innerHTML = text;

            //console.error('JS: updateText: ' + text);
            //updateSvg();
        };
        window.updateText = updateText

        function updateSvg (formula) {
            var svgOutput;
            try {
                svgOutput = window.mj_container.getElementsByTagName('svg')[0].outerHTML;
            }
            catch (err) {
                svgOutput = null;
            }
            window.eq_jax.originalText;

            //svgOutput = document.getElementsByTagName('svg')[0].outerHTML;
            //svgOutput = document.getElementById('mathjax-container').getElementsByTagName('svg')[0].outerHTML;
            //svgOutput = window.mj_container.innerHTML;
            if (svgOutput != null) {
                console.error('JS update SVG, sending back')
                console.error(svgOutput);
                console.error('formula: ' + formula);
                window.handler.sendSvg(formula, svgOutput);
            }
        }
        window.updateSvg = updateSvg

        new QWebChannel(qt.webChannelTransport, function (channel) {
                var handler = channel.objects.handler;
                window.handler = handler;
                updateText(handler.text);
                handler.textChanged.connect(updateText);
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
        mathjax_config = mathjax_v3_config
    elif mathjax_version == '2':
        mathjax_default_url = mathjax_v2_url
        mathjax_config = mathjax_v2_config

    mathjax_url = settings.value("main/mathjaxUrl", mathjax_default_url, type=str)
    html = page_template.format(mj_config=mathjax_v2_config, url=mathjax_url,
                             mj_scripts=mj_v2_scripts, formula='{}')
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

class MathJaxRender(QWebEnginePage):
    def __init__(self):
        super().__init__()
        self.page_template = page_template

        # self.loadFinished.connect(self._on_load_finished)

        self.copy_profile_button.setMenu(self.copy_menu)

    def append_content(self, content):
        # Append the formula to the list box
        content_html= f"{content}<br>"
        if '\\(' in content and '\\)' in content:
            # Use MathJax to render math expressions enclosed in \( and \)
            content_html = content_html.replace('\\(', '<mathjax style="font-size:2.3em" >').replace('\\)', '</mathjax>')
        # js_code = f"document.body.innerHTML += '{content_html}'; MathJax.typeset();"
        # self.text_area.page().runJavaScript(js_code)
        self.eq_list.append_formula(content)

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
        self.runJavaScript("""
            var mjelement = document.getElementById('mathjax-container');
            mjelement.getElementsByTagName('svg')[0].outerHTML;
        """, lambda result: self.update_svg(xml_header + result.encode()))

    def update_svg(self, svg:bytes):
        # add XML header
        formula = self.eq_queue.pop(0)
        self.eq_list.append_formula_svg(formula, svg)

