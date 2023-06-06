
from PyQt5.QtCore import (pyqtProperty, pyqtSignal, pyqtSlot, QEventLoop, QObject, QSettings, Qt,
                          QUrl)
from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineView
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWidgets import qApp
from cairosvg import svg2svg
from io import BytesIO
import matplotlib.pyplot as plt
from cairosvg import svg2svg
#### WA_DontShowOnScreen...  see if this can fix the issue that was causing mathjax not to render
#### when the QWebEnginePage was not being shown in a view.
settings = QSettings()


context = r'''
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
        RR: "{\\bf R}",
        Ex: "{\\operatorname {Ex}}",
        Var: "{\\operatorname {Var}}",
        Cov: "{\\operatorname {Cov}}",
        T: "{\\mathsf{T}}",
        H: "{\\mathsf{H}}",
        range: "{\\operatorname {range}}",
        sech: "{\\operatorname {sech}}",
        csch: "{\\operatorname {csch}}",
        mangle: "{\\operatorname {m}\\angle}",
        bold: ["{\\bf #1}", 1]
      },
      svg: {
        scale: 1,                      // global scaling factor for all expressions
        minScale: .5,                  // smallest scaling factor to use
        mtextInheritFont: false,       // true to make mtext elements use surrounding font
        merrorInheritFont: true,       // true to make merror text use surrounding font
        mathmlSpacing: false,          // true for MathML spacing rules, false for TeX rules
        skipAttributes: {},            // RFDa and other attributes NOT to copy to the output
        exFactor: .5,                  // default size of ex in em units
        displayAlign: 'center',        // default for indentalign when set to 'auto'
        displayIndent: '0',            // default for indentshift when set to 'auto'
        fontCache: 'none',             // or 'global' or 'none'
        localID: null,                 // ID to use for local font cache (for single equation processing)
        internalSpeechTitles: true,    // insert <title> tags with speech content
        titleID: 0                     // initial id number to use for aria-labeledby titles
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
            // const container = document.getElementById('rescale');
            // var w = container.offsetWidth; 
            // var W = container.parentNode.offsetWidth;
            // if (w > W) {
            //     math.style.fontSize = (100*W/w)+"%";
            // }
            // MathJax.startup.document.getMathItemsWithin(math)[0].Rerender();
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
<head>
<div id="placeholder"></div>
<style>.box {{
  width : 100%
  margin: 0 auto 0 auto;
  border: 1px solid black;
  padding: 0 0 0 0 ;
  text-align: center;
}}</style>
</head>
{mj_config}
<script type="text/javascript" src="{url}"></script>
<script type="text/javascript" src="qrc:///qtwebchannel/qwebchannel.js"></script>
</head>
<body>
<div class="box"><div id="rescale" style="display:inline-block">
<mathjax id="mathjax-container" style="font-size:2.3em">\[{formula}\]</mathjax>
</div></div>
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
    return html


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

    def setFormula(self, formula):
        self._formula = formula
        self.formulaChanged.emit(formula)

    def updateFormula(self):
        self.formulaChanged.emit(self._formula)

    def submitFormula(self, formula):
        self._formula = formula
        self.formulaSubmitted.emit(formula)

    text = pyqtProperty(str, fget=text, fset=setText, notify=textChanged)
    formula = pyqtProperty(str, fget=formula, fset=setFormula, notify=formulaChanged)


    @pyqtSlot(str, str)
    def sendSvg(self, formula, svg):
        # called by JS, receives items and sends signal to listener.
        xml_header = b'<?xml version="1.0" encoding="utf-8" standalone="no"?>'
        svg_data = svg2svg(xml_header + svg.encode())
        print(svg_data.decode())
        self.svg_data = svg_data
        self.formula = formula
        self.svgChanged.emit(formula, svg_data)
        self.setFormula('')


class MathJaxRenderer(QWebEnginePage):
    formulaProcessed = pyqtSignal(str, bytes)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = ""
        self.channel = QWebChannel(self)
        self.setWebChannel(self.channel)
        self.handler = CallHandler()
        self.channel.registerObject('handler', self.handler)
        self.setHtml(gen_render_html(), QUrl('file://'))
        self.loadFinished.connect(self._on_load_finished)
        self.handler.svgChanged.connect(self.formulaProcessed.emit)
        # I was thinking this might be something that would fix the MJ2 problems.
        # but actually I couldn't get the problem to manifest so far in this version.
        # and the QWebEnginePage doesn't have a setAttribute method
        ###self.settings().setAttribute(Qt.WA_DontShowOnScreen, True)
        ###self.settings().setAttribute(Qt.WA_DeleteOnClose, True)

    def _on_load_finished(self):
        self.handler.updateFormula()

    def formula(self):
        return self._formula

    def submitFormula(self, formula):
        self.handler.submitFormula(formula)

    formula = pyqtProperty(str, fget=formula, fset=submitFormula, notify=formulaProcessed)

    def updatePreview(self, formula):
        self.handler.setFormula(formula)



class WebSvgRendererX(QWebEngineView):
    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WA_DontShowOnScreen, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.loadFinished.connect(self._on_load_finished)
        self.loop = QEventLoop(qApp)

    def loadSvg(self, svg_data):

        self.processing = True
        self.setHtml(svg_data, QUrl('file://'))

        if self.processing:
            self.loop.exec()

    def _on_load_finished(self):
        if self.processing and self.loop.isRunning():
            self.loop.quit()
        else:
            print('not in event loop, didnt expect this')
