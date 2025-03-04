import sys
import os
import threading
import time
import http.server
import socketserver
import queue
import urllib.parse
from datetime import datetime
from PyQt5.QtCore import QUrl, Qt, QTimer
from PyQt5.QtWidgets import (QApplication, QMainWindow, QToolBar, 
                             QLineEdit, QPushButton, QAction, QVBoxLayout, 
                             QWidget, QTabWidget, QStatusBar, QMessageBox)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtGui import QKeySequence, QPixmap

class WebBrowser(QMainWindow):
    
    def __init__(self):
        super().__init__()
        self.initialize_ui()
        
    def initialize_ui(self):
        self.setWindowTitle("Python Web Browser")
        self.setGeometry(100, 100, 1024, 768)
        
        self.screenshot_dir = os.path.join(os.getcwd(), "screenshots")
        if not os.path.exists(self.screenshot_dir):
            os.makedirs(self.screenshot_dir)
            
        self.command_queue = queue.Queue()
        self.command_timer = QTimer(self)
        self.command_timer.timeout.connect(self.process_commands)
        self.command_timer.start(100)
            
        self.server_port = 8000
        self.start_http_server()
        
        self.auto_screenshot_enabled = True
        self.screenshot_interval = 20
        self.auto_screenshot_timer = QTimer(self)
        self.auto_screenshot_timer.timeout.connect(self.take_auto_screenshot)
        self.auto_screenshot_timer.start(self.screenshot_interval)
        
        self.latest_screenshot = None
        
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        
        self.create_actions()
        self.create_toolbar()
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.add_new_tab()
        self.setCentralWidget(self.tabs)
        self.show()
    
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
        
        self.screenshot_action = QAction("Take Screenshot", self)
        self.screenshot_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_S))
        self.screenshot_action.triggered.connect(self.take_screenshot)
        
        self.auto_screenshot_action = QAction("Toggle Auto-Screenshot", self)
        self.auto_screenshot_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_A))
        self.auto_screenshot_action.triggered.connect(self.toggle_auto_screenshot)
        self.auto_screenshot_action.setCheckable(True)
        self.auto_screenshot_action.setChecked(True)
        
    def create_toolbar(self):
        navigation_bar = QToolBar("Navigation")
        self.addToolBar(navigation_bar)
        
        navigation_bar.addAction(self.back_action)
        navigation_bar.addAction(self.forward_action)
        navigation_bar.addAction(self.reload_action)
        navigation_bar.addAction(self.home_action)
        navigation_bar.addAction(self.new_tab_action)
        navigation_bar.addAction(self.screenshot_action)
        navigation_bar.addAction(self.auto_screenshot_action)
        
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
            
    def take_screenshot(self):
        current_browser = self.get_current_browser()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        url_part = current_browser.url().host().replace(".", "_") or "homepage"
        filename = f"screenshot_{url_part}_{timestamp}.png"
        filepath = os.path.join(self.screenshot_dir, filename)
        
        QTimer.singleShot(500, lambda: self._capture_screenshot(filepath))
        
    def _capture_screenshot(self, filepath):
        current_tab = self.tabs.currentWidget()
        pixmap = current_tab.grab()
        pixmap.save(filepath)
        self.status_bar.showMessage(f"Screenshot saved: {filepath}", 3000)
        self.update_screenshot_index()
        QMessageBox.information(
            self, 
            "Screenshot Captured",
            f"Screenshot saved and available at:\nhttp://localhost:{self.server_port}/{os.path.basename(filepath)}"
        )
        
    def update_screenshot_index(self):
        screenshots = [f for f in os.listdir(self.screenshot_dir) if f.endswith('.png') and f != "live_view.png"]
        screenshots.sort(reverse=True)
        
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Browser Screenshots</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                h1 { color: #333; }
                .live-view-link {
                    display: block;
                    margin: 20px 0;
                    padding: 10px;
                    background-color: #4CAF50;
                    color: white;
                    text-align: center;
                    text-decoration: none;
                    font-weight: bold;
                    border-radius: 5px;
                }
                .live-view-link:hover {
                    background-color: #45a049;
                }
                .screenshot { 
                    margin-bottom: 30px; 
                    padding: 10px;
                    border: 1px solid #ddd;
                    border-radius: 5px;
                }
                .screenshot img { 
                    max-width: 100%;
                    border: 1px solid #eee;
                }
                .timestamp { 
                    color: #666; 
                    font-size: 0.8em;
                    margin-bottom: 5px;
                }
            </style>
        </head>
        <body>
            <h1>Browser Screenshots</h1>
            <a href="live_view.html" class="live-view-link">View Live Stream (Auto-updating every 100ms)</a>
        """
        for screenshot in screenshots:
            timestamp_str = screenshot.split('_')[-1].split('.')[0]
            date_str = screenshot.split('_')[-2]
            formatted_time = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]} {timestamp_str[:2]}:{timestamp_str[2:4]}:{timestamp_str[4:]}"
            html_content += f"""
            <div class="screenshot">
                <div class="timestamp">Captured: {formatted_time}</div>
                <img src="{screenshot}" alt="Screenshot {screenshot}">
            </div>
            """
        html_content += "</body></html>"
        with open(os.path.join(self.screenshot_dir, "index.html"), "w") as f:
            f.write(html_content)
            
    def start_http_server(self):
        class ScreenshotHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=self.server_directory, **kwargs)
                
            def log_message(self, format, *args):
                pass
                
            def end_headers(self):
                path = self.path.split('?')[0]
                if path.endswith('/live_view.png'):
                    self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
                    self.send_header('Pragma', 'no-cache')
                    self.send_header('Expires', '0')
                super().end_headers()
                
            def do_GET(self):
                if self.path.startswith('/navigate?'):
                    query = self.path.split('?')[1]
                    params = urllib.parse.parse_qs(query)
                    url = params.get('url', [''])[0]
                    if url:
                        self.server.command_queue.put(('navigate', url))
                        self.send_response(302)
                        self.send_header('Location', '/live_view.html')
                        self.end_headers()
                    else:
                        self.send_response(400)
                        self.end_headers()
                        self.wfile.write(b'Missing url parameter')
                elif self.path.startswith('/switch_tab?'):
                    query = self.path.split('?')[1]
                    params = urllib.parse.parse_qs(query)
                    direction = params.get('direction', [''])[0]
                    if direction in ['prev', 'next']:
                        self.server.command_queue.put(('switch_tab', direction))
                        self.send_response(302)
                        self.send_header('Location', '/live_view.html')
                        self.end_headers()
                    else:
                        self.send_response(400)
                        self.end_headers()
                        self.wfile.write(b'Invalid direction')
                elif self.path.startswith('/click?'):
                    query = self.path.split('?')[1]
                    params = urllib.parse.parse_qs(query)
                    x = params.get('x', [''])[0]
                    y = params.get('y', [''])[0]
                    if x and y:
                        try:
                            x, y = int(x), int(y)
                            self.server.command_queue.put(('click', x, y))
                            self.send_response(200)
                            self.end_headers()
                        except ValueError:
                            self.send_response(400)
                            self.end_headers()
                            self.wfile.write(b'Invalid coordinates')
                    else:
                        self.send_response(400)
                        self.end_headers()
                        self.wfile.write(b'Missing x or y parameter')
                elif self.path.startswith('/scroll?'):
                    query = self.path.split('?')[1]
                    params = urllib.parse.parse_qs(query)
                    direction = params.get('direction', [''])[0]
                    amount = params.get('amount', [''])[0]
                    if direction in ['up', 'down'] and amount:
                        try:
                            amount = int(amount)
                            self.server.command_queue.put(('scroll', direction, amount))
                            self.send_response(200)
                            self.end_headers()
                        except ValueError:
                            self.send_response(400)
                            self.end_headers()
                            self.wfile.write(b'Invalid amount')
                    else:
                        self.send_response(400)
                        self.end_headers()
                        self.wfile.write(b'Invalid direction or missing amount')
                elif self.path.startswith('/type?'):
                    query = self.path.split('?')[1]
                    params = urllib.parse.parse_qs(query)
                    key = params.get('key', [''])[0]
                    if key:
                        self.server.command_queue.put(('type', key))
                        self.send_response(200)
                        self.end_headers()
                    else:
                        self.send_response(400)
                        self.end_headers()
                        self.wfile.write(b'Missing key parameter')
                else:
                    super().do_GET()
        
        ScreenshotHandler.server_directory = self.screenshot_dir
        self.update_live_view_page()
        
        def run_server():
            with socketserver.TCPServer(("", self.server_port), ScreenshotHandler) as httpd:
                httpd.command_queue = self.command_queue
                print(f"Serving screenshots at http://localhost:{self.server_port}")
                print(f"Live view available at http://localhost:{self.server_port}/live_view.html")
                httpd.serve_forever()
                
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        time.sleep(0.5)

    def take_auto_screenshot(self):
        if not self.auto_screenshot_enabled:
            return
        current_tab = self.tabs.currentWidget()
        pixmap = current_tab.grab()
        live_filename = "live_view.png"
        filepath = os.path.join(self.screenshot_dir, live_filename)
        pixmap.save(filepath)
        self.update_live_view_page()
        self.latest_screenshot = filepath
        
    def toggle_auto_screenshot(self):
        self.auto_screenshot_enabled = not self.auto_screenshot_enabled
        if self.auto_screenshot_enabled:
            self.auto_screenshot_timer.start(self.screenshot_interval)
            self.status_bar.showMessage("Auto-screenshots enabled", 2000)
        else:
            self.auto_screenshot_timer.stop()
            self.status_bar.showMessage("Auto-screenshots disabled", 2000)
        self.auto_screenshot_action.setChecked(self.auto_screenshot_enabled)
        
    def update_live_view_page(self):
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Browser Live View</title>
            <style>
                body { 
                    font-family: Arial, sans-serif; 
                    margin: 0; 
                    padding: 0;
                    background-color: #f0f0f0;
                    text-align: center;
                }
                h1 { 
                    color: #333; 
                    padding: 20px;
                    margin: 0;
                    background-color: #e0e0e0;
                }
                .control-panel {
                    margin: 20px auto;
                    text-align: center;
                }
                .scroll-buttons {
                    margin-top: 10px;
                }
                .live-view {
                    margin: 20px auto;
                    max-width: 95%;
                    box-shadow: 0 0 10px rgba(0,0,0,0.1);
                }
                .live-view img {
                    width: 100%;
                    border: 1px solid #ddd;
                }
                .refresh-note {
                    color: #666;
                    font-size: 0.9em;
                    margin-top: 10px;
                }
                .auto-refresh {
                    color: green;
                    font-weight: bold;
                }
            </style>
            <script>
                function refreshImage() {
                    const img = document.getElementById('live-image');
                    img.src = 'live_view.png?t=' + new Date().getTime();
                }
                setInterval(refreshImage, 100);

                function handleClick(event) {
                    const img = document.getElementById('live-image');
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
                    const key = event.key;
                    fetch(`/type?key=${encodeURIComponent(key)}`);
                });

                document.addEventListener('DOMContentLoaded', function() {
                    const img = document.getElementById('live-image');
                    img.addEventListener('click', handleClick);
                });
            </script>
        </head>
        <body>
            <h1>Browser Live View</h1>
            <div class="control-panel">
                <form action="/navigate" method="get">
                    <input type="text" name="url" placeholder="Enter URL" style="width: 300px;">
                    <button type="submit">Go</button>
                </form>
                <button onclick="location.href='/switch_tab?direction=prev'">Previous Tab</button>
                <button onclick="location.href='/switch_tab?direction=next'">Next Tab</button>
                <div class="scroll-buttons">
                    <button onclick="scroll('up', 100)">Scroll Up</button>
                    <button onclick="scroll('down', 100)">Scroll Down</button>
                </div>
            </div>
            <div class="live-view">
                <img id="live-image" src="live_view.png" alt="Live Browser View">
            </div>
            <p class="refresh-note">
                <span class="auto-refresh">Auto-refreshing</span> every 100ms
            </p>
        </body>
        </html>
        """
        with open(os.path.join(self.screenshot_dir, "live_view.html"), "w") as f:
            f.write(html_content)
            
    def process_commands(self):
        while not self.command_queue.empty():
            command, *args = self.command_queue.get()
            if command == 'navigate':
                url = args[0]
                self.load_url(url)
            elif command == 'switch_tab':
                direction = args[0]
                current_index = self.tabs.currentIndex()
                if direction == 'prev':
                    new_index = (current_index - 1) % self.tabs.count()
                elif direction == 'next':
                    new_index = (current_index + 1) % self.tabs.count()
                self.tabs.setCurrentIndex(new_index)
            elif command == 'click':
                x, y = args
                self.simulate_click(x, y)
            elif command == 'scroll':
                direction, amount = args
                self.simulate_scroll(direction, amount)
            elif command == 'type':
                key = args[0]
                self.simulate_key_press(key)

    def simulate_click(self, x, y):
        current_browser = self.get_current_browser()
        js_code = f"""
        var el = document.elementFromPoint({x}, {y});
        if (el) el.click();
        """
        current_browser.page().runJavaScript(js_code)

    def simulate_scroll(self, direction, amount):
        current_browser = self.get_current_browser()
        scroll_amount = amount if direction == 'down' else -amount
        current_browser.page().runJavaScript(f"window.scrollBy(0, {scroll_amount});")

    def simulate_key_press(self, key):
        current_browser = self.get_current_browser()
        key_escaped = key.replace("'", "\\'")
        shift = 'true' if key == 'Shift' else 'false'
        ctrl = 'true' if key == 'Control' else 'false'
        alt = 'true' if key == 'Alt' else 'false'
        meta = 'true' if key == 'Meta' else 'false'
        
        js_code = f"""
        var activeEl = document.activeElement;
        var eventObj = new KeyboardEvent('keydown', {{
            key: '{key_escaped}',
            shiftKey: {shift},
            ctrlKey: {ctrl},
            altKey: {alt},
            metaKey: {meta},
            bubbles: true
        }});
        
        if ('{key_escaped}' === 'Backspace' && (activeEl.tagName === 'INPUT' || activeEl.tagName === 'TEXTAREA')) {{
            if (activeEl.value.length > 0) {{
                activeEl.value = activeEl.value.slice(0, -1);
            }}
        }} else if ('{key_escaped}' === 'Enter') {{
            activeEl.dispatchEvent(eventObj);
            if (activeEl.tagName === 'INPUT' && activeEl.form) {{
                activeEl.form.dispatchEvent(new Event('submit', {{ bubbles: true }}));
            }}
        }} else if (!['Shift', 'Control', 'Alt', 'Meta'].includes('{key_escaped}')) {{
            if (activeEl.tagName === 'INPUT' || activeEl.tagName === 'TEXTAREA') {{
                activeEl.value += '{key_escaped}';
            }}
            activeEl.dispatchEvent(eventObj);
        }} else {{
            activeEl.dispatchEvent(eventObj);
        }}
        """
        current_browser.page().runJavaScript(js_code)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    browser = WebBrowser()
    print(f"Screenshot server running at http://localhost:{browser.server_port}")
    print(f"Live view available at http://localhost:{browser.server_port}/live_view.html")
    sys.exit(app.exec_())