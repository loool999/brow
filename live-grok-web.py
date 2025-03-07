import sys
import os
import threading
import time
import http.server
import socketserver
import queue
import urllib.parse
import json
from PyQt5.QtCore import QUrl, Qt, QTimer, QBuffer
from PyQt5.QtWidgets import (QApplication, QMainWindow, QToolBar, 
                             QLineEdit, QPushButton, QAction, QVBoxLayout, 
                             QWidget, QTabWidget, QStatusBar)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtGui import QKeySequence, QPixmap, QImage

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass

class WebBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        # Threading synchronization for streaming
        self.image_lock = threading.Lock()
        self.image_condition = threading.Condition(self.image_lock)
        self.latest_image = None
        self.initialize_ui()

    def initialize_ui(self):
        self.setWindowTitle("Python Web Browser")
        self.setGeometry(100, 100, 1024, 768)

        # Create server directory
        self.server_dir = os.path.join(os.getcwd(), "server_files")
        if not os.path.exists(self.server_dir):
            os.makedirs(self.server_dir)

        # Write static index.html
        self.write_static_html()

        self.command_queue = queue.Queue()
        self.command_timer = QTimer(self)
        self.command_timer.timeout.connect(self.process_commands)
        self.command_timer.start(100)

        self.server_port = 8000

        # Setup streaming
        self.stream_enabled = True
        self.stream_interval = 25  # 25fps
        self.stream_timer = QTimer(self)
        self.stream_timer.timeout.connect(self.update_stream)
        self.stream_timer.start(self.stream_interval)

        # Setup tabs
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)

        self.create_actions()
        self.create_toolbar()

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.add_new_tab()
        self.setCentralWidget(self.tabs)

        # Start HTTP server
        self.start_http_server()

        self.show()

    def write_static_html(self):
        html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: #f0f0f0; text-align: center; }
            h1 { color: #333; padding: 20px; margin: 0; background-color: #e0e0e0; }
            .control-panel { margin: 20px auto; text-align: center; }
            .scroll-buttons { margin-top: 10px; }
            .browser-view { margin: 20px auto; max-width: 95%; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
            .browser-view img { width: 100%; border: 1px solid #ddd; }
        </style>
        <script>
            function handleClick(event) {
                const img = document.getElementById('stream-image');
                const rect = img.getBoundingClientRect();
                const x = event.clientX - rect.left;
                const y = event.clientY - rect.top;
                const scaleX = img.naturalWidth / rect.width;
                const scaleY = img.naturalHeight / rect.height;
                const actualX = Math.round(x * scaleX);
                const actualY = Math.round(y * scaleY);
                fetch(`/click?x=${actualX}&y=${actualY}`);
            }

            function scroll(direction, amount) {
                fetch(`/scroll?direction=${direction}&amount=${amount}`);
            }

            document.addEventListener('keydown', function(event) {
                event.preventDefault();
                const key = event.key;
                const modifiers = {
                    ctrl: event.ctrlKey,
                    shift: event.shiftKey,
                    alt: event.altKey
                };
                fetch(`/type?key=${encodeURIComponent(key)}&modifiers=${encodeURIComponent(JSON.stringify(modifiers))}`);
            });

            document.addEventListener('wheel', function(event) {
                event.preventDefault();
                const direction = event.deltaY > 0 ? 'down' : 'up';
                const amount = Math.abs(event.deltaY);
                scroll(direction, amount);
            });

            document.addEventListener('DOMContentLoaded', function() {
                const img = document.getElementById('stream-image');
                img.addEventListener('click', handleClick);
            });
        </script>
    </head>
    <body>
        <div class="control-panel">
            <form action="/navigate" method="get">
                <input type="text" name="url" placeholder="Enter URL" style="width: 300px;">
                <button type="submit">Go</button>
            </form>
            <button onclick="location.href='/switch_tab?direction=prev'">Previous Tab</button>
            <button onclick="location.href='/switch_tab?direction=next'">Next Tab</button>
            </div>
            <div class="browser-view">
                <img id="stream-image" src="/stream" alt="Browser Stream View">
            </div>
        </body>
        </html>
        """
        with open(os.path.join(self.server_dir, "index.html"), "w") as f:
            f.write(html_content)

    def create_actions(self):
        self.back_action = QAction("Back", self)
        self.back_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_Left))
        self.back_action.triggered.connect(self.navigate_back)

        self.forward_action = QAction("Forward", self)
        self.forward_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_Right))
        self.forward_action.triggered.connect(self.navigate_forward)

        self.reload_action = QAction("Reload", self)
        self.reload_action.setShortcut(QKeySequence(Qt.Key_F5))
        self.reload_action.triggered.connect(self.reload_page)

        self.home_action = QAction("Home", self)
        self.home_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_H))
        self.home_action.triggered.connect(self.navigate_home)

        self.new_tab_action = QAction("New Tab", self)
        self.new_tab_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_T))
        self.new_tab_action.triggered.connect(self.add_new_tab)

        self.toggle_stream_action = QAction("Toggle Stream", self)
        self.toggle_stream_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_A))
        self.toggle_stream_action.triggered.connect(self.toggle_stream)
        self.toggle_stream_action.setCheckable(True)
        self.toggle_stream_action.setChecked(True)

    def create_toolbar(self):
        navigation_bar = QToolBar("Navigation")
        self.addToolBar(navigation_bar)

        navigation_bar.addAction(self.back_action)
        navigation_bar.addAction(self.forward_action)
        navigation_bar.addAction(self.reload_action)
        navigation_bar.addAction(self.home_action)
        navigation_bar.addAction(self.new_tab_action)
        navigation_bar.addAction(self.toggle_stream_action)

        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        navigation_bar.addWidget(self.url_bar)

        go_button = QPushButton("Go")
        go_button.clicked.connect(self.navigate_to_url)
        navigation_bar.addWidget(go_button)

    def add_new_tab(self, url=None):
        browser = QWebEngineView()
        browser.page().loadProgress.connect(self.update_loading_progress)
        browser.page().loadFinished.connect(self.update_url)
        browser.page().titleChanged.connect(self.update_title)

        layout = QVBoxLayout()
        layout.addWidget(browser)
        layout.setContentsMargins(0, 0, 0, 0)

        tab = QWidget()
        tab.setLayout(layout)

        index = self.tabs.addTab(tab, "New Tab")
        self.tabs.setCurrentIndex(index)

        if url:
            browser.load(QUrl(url))
        else:
            browser.load(QUrl("https://www.google.com"))

    def close_tab(self, index):
        if self.tabs.count() > 1:
            self.tabs.removeTab(index)
        else:
            current_browser = self.get_current_browser()
            current_browser.load(QUrl("https://www.google.com"))

    def get_current_browser(self):
        current_tab = self.tabs.currentWidget()
        layout = current_tab.layout()
        return layout.itemAt(0).widget()

    def navigate_to_url(self):
        url = self.url_bar.text()
        self.load_url(url)

    def load_url(self, url):
        if not url.startswith(("http://", "https://")):
            url = "http://" + url
        current_browser = self.get_current_browser()
        current_browser.load(QUrl(url))

    def navigate_back(self):
        current_browser = self.get_current_browser()
        current_browser.back()

    def navigate_forward(self):
        current_browser = self.get_current_browser()
        current_browser.forward()

    def reload_page(self):
        current_browser = self.get_current_browser()
        current_browser.reload()

    def navigate_home(self):
        current_browser = self.get_current_browser()
        current_browser.load(QUrl("https://www.google.com"))

    def update_url(self):
        current_browser = self.get_current_browser()
        self.url_bar.setText(current_browser.url().toString())

    def update_title(self, title):
        index = self.tabs.currentIndex()
        if title:
            self.tabs.setTabText(index, title[:15] + "..." if len(title) > 15 else title)

    def update_loading_progress(self, progress):
        self.status_bar.showMessage(f"Loading: {progress}%")
        if progress == 100:
            self.status_bar.showMessage("Done", 2000)

    def update_stream(self):
        if not self.stream_enabled:
            return
        current_tab = self.tabs.currentWidget()
        pixmap = current_tab.grab()
        image = QImage(pixmap.toImage())
        buffer = QBuffer()
        buffer.open(QBuffer.ReadWrite)
        image.save(buffer, "JPEG", quality=70)
        image_bytes = bytes(buffer.data())
        with self.image_lock:
            self.latest_image = image_bytes
            self.image_condition.notify_all()

    def toggle_stream(self):
        self.stream_enabled = not self.stream_enabled
        if self.stream_enabled:
            self.stream_timer.start(self.stream_interval)
            self.status_bar.showMessage("Stream enabled", 2000)
        else:
            self.stream_timer.stop()
            self.status_bar.showMessage("Stream disabled", 2000)
        self.toggle_stream_action.setChecked(self.stream_enabled)

    def start_http_server(self):
        class BrowserHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                self.browser = kwargs.pop('browser', None)
                self.server_directory = kwargs.pop('directory', None)
                super().__init__(*args, **kwargs)

            def log_message(self, format, *args):
                pass  # Suppress server logs

            def do_GET(self):
                if self.path == '/stream':
                    self.send_response(200)
                    self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
                    self.end_headers()
                    try:
                        while True:
                            with self.browser.image_lock:
                                self.browser.image_condition.wait()
                                image_bytes = self.browser.latest_image
                            self.wfile.write(b'--frame\r\n')
                            self.wfile.write(b'Content-Type: image/jpeg\r\n\r\n')
                            self.wfile.write(image_bytes)
                            self.wfile.write(b'\r\n')
                    except Exception as e:
                        print(f"Stream closed: {e}")
                elif self.path.startswith('/navigate?'):
                    query = self.path.split('?')[1]
                    params = urllib.parse.parse_qs(query)
                    url = params.get('url', [''])[0]
                    if url:
                        self.browser.command_queue.put(('navigate', url))
                    self.send_response(303)
                    self.send_header('Location', '/')
                    self.end_headers()
                elif self.path.startswith('/scroll?'):
                    query = self.path.split('?')[1]
                    params = urllib.parse.parse_qs(query)
                    direction = params.get('direction', [''])[0]
                    amount = int(params.get('amount', [100])[0])
                    self.browser.command_queue.put(('scroll', direction, amount))
                    self.send_response(200)
                    self.end_headers()
                elif self.path.startswith('/type?'):
                    query = self.path.split('?')[1]
                    params = urllib.parse.parse_qs(query)
                    key = urllib.parse.unquote(params.get('key', [''])[0])
                    modifiers = json.loads(urllib.parse.unquote(params.get('modifiers', ['{}'])[0]))
                    self.browser.command_queue.put(('type', key, modifiers))
                    self.send_response(200)
                    self.end_headers()
                elif self.path.startswith('/click?'):
                    query = self.path.split('?')[1]
                    params = urllib.parse.parse_qs(query)
                    x = int(params.get('x', [0])[0])
                    y = int(params.get('y', [0])[0])
                    self.browser.command_queue.put(('click', x, y))
                    self.send_response(200)
                    self.end_headers()
                else:
                    super().do_GET()

        # Create a factory function to pass the browser and directory to the handler
        def handler_factory(*args, **kwargs):
            kwargs['browser'] = self
            kwargs['directory'] = self.server_dir
            return BrowserHandler(*args, **kwargs)

        self.server = ThreadedTCPServer(("", self.server_port), handler_factory)
        server_thread = threading.Thread(target=self.server.serve_forever)
        server_thread.daemon = True
        server_thread.start()

        def run_server():
            with ThreadedTCPServer(("0.0.0.0", self.server_port), BrowserHandler) as httpd:
                httpd.command_queue = self.command_queue
                print(f"Browser stream server running at http://0.0.0.0:{self.server_port}")
                httpd.serve_forever()

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        time.sleep(0.5)

    def handle_click(self, x, y):
        current_browser = self.get_current_browser()

        if not current_browser or not current_browser.page():
            print("Error: No valid browser or page found.")
            return
    
        js_code = f"""
            (function() {{
                var element = document.elementFromPoint({x}, {y});
                if (element) {{
                    var clickEvent = new MouseEvent('click', {{
                        bubbles: true,
                        cancelable: true,
                        view: window,
                        clientX: {x},
                        clientY: {y}
                    }});
                    element.dispatchEvent(clickEvent);
                }}
            }})();
        """

        current_browser.page().runJavaScript(js_code)


    def process_commands(self):
        try:
            while not self.command_queue.empty():
                command = self.command_queue.get_nowait()
                if command[0] == 'navigate':
                    self.load_url(command[1])
                elif command[0] == 'scroll':
                    self.handle_scroll(command[1], command[2])
                elif command[0] == 'type':
                    self.handle_key_press(command[1], command[2])
                elif command[0] == 'click':
                    self.handle_click(command[1], command[2])
                self.command_queue.task_done()
        except queue.Empty:
            pass

    def handle_scroll(self, direction, amount):
        current_browser = self.get_current_browser()
        if direction == 'up':
            current_browser.page().runJavaScript(f"window.scrollBy(0, -{amount});")
        elif direction == 'down':
            current_browser.page().runJavaScript(f"window.scrollBy(0, {amount});")
    def handle_key_press(self, key, modifiers):
        current_browser = self.get_current_browser()
        key_escaped = key.replace("'", "\\'")
        shift = 'true' if key == 'Shift' else 'false'
        ctrl = 'true' if key == 'Control' else 'false'
        alt = 'true' if key == 'Alt' else 'false'
        meta = 'true' if key == 'Meta' else 'false'

        js_code = f"""
        (function() {{
            var activeEl = document.activeElement;
            if (!activeEl) return;

            if ('{key_escaped}' === 'Enter') {{
                var keyDownEvent = new KeyboardEvent('keydown', {{
                    key: 'Enter',
                    code: 'Enter',
                    keyCode: 13,
                    which: 13,
                    shiftKey: {shift},
                    ctrlKey: {ctrl},
                    altKey: {alt},
                    metaKey: {meta},
                    bubbles: true,
                    cancelable: true
                }});
                activeEl.dispatchEvent(keyDownEvent);

                var keyUpEvent = new KeyboardEvent('keyup', {{
                    key: 'Enter',
                    code: 'Enter',
                    keyCode: 13,
                    which: 13,
                    shiftKey: {shift},
                    ctrlKey: {ctrl},
                    altKey: {alt},
                    metaKey: {meta},
                    bubbles: true,
                    cancelable: true
                }});
                activeEl.dispatchEvent(keyUpEvent);

                if (activeEl.tagName === 'INPUT' && activeEl.form) {{
                    activeEl.form.submit();
                }}
            }} else if ('{key_escaped}' === 'Backspace' && (activeEl.tagName === 'INPUT' || activeEl.tagName === 'TEXTAREA')) {{
                if (activeEl.value.length > 0) {{
                    activeEl.value = activeEl.value.slice(0, -1);
                }}
                var keyDownEvent = new KeyboardEvent('keydown', {{
                    key: 'Backspace',
                    code: 'Backspace',
                    keyCode: 8,
                    which: 8,
                    bubbles: true,
                    cancelable: true
                }});
                activeEl.dispatchEvent(keyDownEvent);
            }} else {{
                var keyDownEvent = new KeyboardEvent('keydown', {{
                    key: '{key_escaped}',
                    code: '{key_escaped}',
                    bubbles: true,
                    cancelable: true,
                    shiftKey: {shift},
                    ctrlKey: {ctrl},
                    altKey: {alt},
                    metaKey: {meta}
                }});
                activeEl.dispatchEvent(keyDownEvent);
                if (!['Shift', 'Control', 'Alt', 'Meta', 'Enter', 'Backspace'].includes('{key_escaped}')) {{
                    if (activeEl.tagName === 'INPUT' || activeEl.tagName === 'TEXTAREA') {{
                        activeEl.value += '{key_escaped}';
                    }}
                }}
            }}
        }})();
        """
        current_browser.page().runJavaScript(js_code)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    browser = WebBrowser()
    print(f"Browser stream server running at http://localhost:{browser.server_port}")
    sys.exit(app.exec_())

#xvfb-run /home/codespace/.python/current/bin/python /workspaces/brow/live-grok-web.py