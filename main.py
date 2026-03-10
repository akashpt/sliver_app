import sys
import os

from PyQt5.QtWidgets import QApplication
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtCore import QUrl

from bridge_up import Bridge


app = QApplication(sys.argv) 
app.setApplicationName("Sliver Strip Detection")

view = QWebEngineView()

# Bridge setup
channel = QWebChannel()
bridge = Bridge()

channel.registerObject("bridge", bridge)
view.page().setWebChannel(channel)

# HTML Path (Relative Path ⭐ Important)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
html_path = os.path.join(BASE_DIR, "templates", "index.html")

view.load(QUrl.fromLocalFile(html_path))

view.resize(1200, 800)
view.show()

app.aboutToQuit.connect(bridge.stopDetection)

sys.exit(app.exec_())






























# # main.py
# import sys
# import os
# from PyQt5.QtWidgets import QApplication
# from PyQt5.QtWebEngineWidgets import QWebEngineView
# from PyQt5.QtWebChannel import QWebChannel
# from PyQt5.QtCore import QUrl
# from bridge import Bridge  # your Bridge class that requires a view

# def resource_path(relative_path):
#     """ Get absolute path to resource, works for dev and for PyInstaller """
#     try:
#         # PyInstaller stores path in _MEIPASS when bundled
#         base_path = sys._MEIPASS
#     except Exception:
#         # During normal development, use the directory of the script
#         base_path = os.path.abspath(".")
#     return os.path.join(base_path, relative_path)


# app = QApplication(sys.argv)

# view = QWebEngineView()  # create the view

# channel = QWebChannel()
# bridge = Bridge()    # pass the view here

# channel.registerObject("bridge", bridge)
# view.page().setWebChannel(channel)

# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# html = os.path.join(BASE_DIR, "templates", "index.html")
# view.load(QUrl.fromLocalFile(html))

# view.resize(1200, 800)
# view.show()

# app.aboutToQuit.connect(bridge.stopDetection)
# sys.exit(app.exec_())
