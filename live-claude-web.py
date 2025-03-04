import sys
import os
import threading
import time
import http.server
import socketserver
import queue
import urllib.parse
from PyQt5.QtCore import QUrl, Qt, QTimer, QByteArray, QIODevice, QBuffer
from PyQt5.QtWidgets import (QApplication, QMainWindow, QToolBar, 
                             QLineEdit, QPushButton, QAction, QVBoxLayout, 
                             QWidget, QTabWidget, QStatusBar,)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtGui import QKeySequence, QImage
import base64

class WebBrowser(QMainWindow):
    
    def __init__(self):
        super().__init__()
        self.initialize_ui()
        
    def initialize_ui(self):
        self.setWindowTitle("Python Web Browser")
        self.setGeometry(100, 100, 1024, 768)
        
        # Create directory for web server files
        self.server_dir = os.path.join(os.getcwd(), "server_files")
        if not os.path.exists(self.server_dir):
            os.makedirs(self.server_dir)
            
        self.command_queue = queue.Queue()
        self.command_timer = QTimer(self)
        self.command_timer.timeout.connect(self.process_commands)
        self.command_timer.start(100)
            
        self.server_port = 8000
        
        # Setup direct streaming
        self.stream_enabled = True
        self.stream_interval = 40  # 40ms for smoother streaming
        self.stream_timer = QTimer(self)
        self.stream_timer.timeout.connect(self.update_stream)
        self.stream_timer.start(self.stream_interval)
        
        # Latest image data for streaming
        self.latest_image_data = None
        
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
        
        # Start the HTTP server
        self.start_http_server()
        
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
        """Capture the current browser state and send to connected clients"""
        if not self.stream_enabled:
            return
            
        # Capture the current browser window
        current_tab = self.tabs.currentWidget()
        if not current_tab:
            return
            
        # Capture current tab content
        pixmap = current_tab.grab()
        image = QImage(pixmap.toImage())
        
        # Convert to more efficient image format for streaming
        byte_array = QByteArray()
        buffer = QBuffer(byte_array)
        buffer.open(QIODevice.WriteOnly)
        image.save(buffer, "JPEG", 85)  # JPEG with 85% quality
        buffer.close()
        
        # Get the base64 encoded data
        self.latest_image_data = base64.b64encode(byte_array.data()).decode('utf-8')
        
        # Create the streaming HTML file if needed
        if not os.path.exists(os.path.join(self.server_dir, "index.html")):
            self.create_streaming_page()
            
    def toggle_stream(self):
        self.stream_enabled = not self.stream_enabled
        if self.stream_enabled:
            self.stream_timer.start(self.stream_interval)
            self.status_bar.showMessage("Stream enabled", 2000)
        else:
            self.stream_timer.stop()
            self.status_bar.showMessage("Stream disabled", 2000)
        self.toggle_stream_action.setChecked(self.stream_enabled)
        
    def create_streaming_page(self):
        """Create the HTML page with WebSocket for direct streaming"""
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Browser Live Stream</title>
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
                    padding: 15px;
                    margin: 0;
                    background-color: #e0e0e0;
                }
                .control-panel {
                    margin: 10px auto;
                    padding: 10px;
                    background-color: #f8f8f8;
                    border-radius: 5px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                }
                .scroll-buttons {
                    margin-top: 10px;
                }
                .browser-view {
                    margin: 10px auto;
                    max-width: 95%;
                    box-shadow: 0 0 10px rgba(0,0,0,0.1);
                    position: relative;
                    background-color: #fff;
                    border-radius: 3px;
                }
                .browser-view img {
                    width: 100%;
                    border: 1px solid #ddd;
                    border-radius: 3px;
                }
                button {
                    padding: 5px 10px;
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 3px;
                    cursor: pointer;
                    margin: 0 2px;
                }
                button:hover {
                    background-color: #45a049;
                }
                input[type="text"] {
                    padding: 5px;
                    border: 1px solid #ddd;
                    border-radius: 3px;
                    margin-right: 5px;
                }
                .status {
                    color: #666;
                    font-size: 0.9em;
                    margin-top: 5px;
                }
                .active {
                    color: green;
                    font-weight: bold;
                }
            </style>
            <script>
                // Use EventSource for Server-Sent Events (SSE)
                let evtSource;
                let streamActive = true;
                
                function setupStream() {
                    if (!streamActive) return;
                    
                    evtSource = new EventSource('/stream');
                    
                    evtSource.onmessage = function(event) {
                        const img = document.getElementById('stream-image');
                        img.src = 'data:image/jpeg;base64,' + event.data;
                    };
                    
                    evtSource.onerror = function() {
                        console.log("SSE connection failed, reconnecting...");
                        evtSource.close();
                        setTimeout(setupStream, 1000);
                    };
                    
                    document.getElementById('status').textContent = 'Connected';
                    document.getElementById('status').className = 'active';
                }
                
                function toggleStream() {
                    streamActive = !streamActive;
                    if (streamActive) {
                        setupStream();
                        document.getElementById('toggle-btn').textContent = 'Pause Stream';
                    } else {
                        evtSource.close();
                        document.getElementById('status').textContent = 'Paused';
                        document.getElementById('status').className = '';
                        document.getElementById('toggle-btn').textContent = 'Resume Stream';
                    }
                }

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
                    // Only capture when user is not typing in the URL box
                    if (document.activeElement.tagName !== 'INPUT') {
                        fetch(`/type?key=${encodeURIComponent(event.key)}`);
                        event.preventDefault();
                    }
                });

                document.addEventListener('DOMContentLoaded', function() {
                    const img = document.getElementById('stream-image');
                    img.addEventListener('click', handleClick);
                    setupStream();
                    
                    document.getElementById('url-form').addEventListener('submit', function(e) {
                        const urlInput = document.getElementById('url-input');
                        if (urlInput.value.trim() === '') {
                            e.preventDefault();
                        }
                    });
                });
            </script>
        </head>
        <body>
            <h1>Browser Live Stream</h1>
            <div class="control-panel">
                <form id="url-form" action="/navigate" method="get">
                    <input id="url-input" type="text" name="url" placeholder="Enter URL" style="width: 300px;">
                    <button type="submit">Go</button>
                </form>
                <div style="margin-top: 5px;">
                    <button onclick="location.href='/back'" title="Go back">←</button>
                    <button onclick="location.href='/forward'" title="Go forward">→</button>
                    <button onclick="location.href='/reload'" title="Reload page">↻</button>
                    <button onclick="location.href='/home'" title="Home">🏠</button>
                    <button onclick="location.href='/switch_tab?direction=prev'">Previous Tab</button>
                    <button onclick="location.href='/switch_tab?direction=next'">Next Tab</button>
                    <button onclick="location.href='/new_tab'">New Tab</button>
                </div>
                <div class="scroll-buttons">
                    <button onclick="scroll('up', 100)">Scroll Up</button>
                    <button onclick="scroll('down', 100)">Scroll Down</button>
                    <button id="toggle-btn" onclick="toggleStream()">Pause Stream</button>
                </div>
                <div class="status">
                    Stream status: <span id="status" class="active">Connected</span>
                </div>
            </div>
            <div class="browser-view">
                <img id="stream-image" src="/placeholder.png" alt="Browser Stream View">
            </div>
        </body>
        </html>
        """
        
        # Write the HTML file with utf-8 encoding
        with open(os.path.join(self.server_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html_content)
            
        # Create a placeholder image
        placeholder_html = '<svg width="800" height="600" xmlns="http://www.w3.org/2000/svg"><rect width="100%" height="100%" fill="#f0f0f0"/><text x="50%" y="50%" font-family="Arial" font-size="24" text-anchor="middle" fill="#666">Loading stream...</text></svg>'
        placeholder_path = os.path.join(self.server_dir, "placeholder.png")
        with open(placeholder_path, "w", encoding="utf-8") as f:
            f.write(placeholder_html)
            
    def start_http_server(self):
        class StreamHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=self.server_directory, **kwargs)
                
            def log_message(self, format, *args):
                pass  # Suppress server logs
                
            def do_GET(self):
                # Server-Sent Events (SSE) endpoint for streaming
                if self.path == '/stream':
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/event-stream')
                    self.send_header('Cache-Control', 'no-cache')
                    self.send_header('Connection', 'keep-alive')
                    self.end_headers()
                    
                    try:
                        while True:
                            if hasattr(self.server, 'get_latest_image'):
                                image_data = self.server.get_latest_image()
                                if image_data:
                                    self.wfile.write(f"data: {image_data}\n\n".encode('utf-8'))
                                    self.wfile.flush()
                            time.sleep(0.05)  # 50ms update interval
                    except (ConnectionAbortedError, BrokenPipeError):
                        pass  # Client disconnected
                    return
                
                elif self.path.startswith('/navigate?'):
                    query = self.path.split('?')[1]
                    params = urllib.parse.parse_qs(query)
                    url = params.get('url', [''])[0]
                    if url:
                        self.server.command_queue.put(('navigate', url))
                        self.send_response(302)
                        self.send_header('Location', '/')
                        self.end_headers()
                    else:
                        self.send_response(400)
                        self.end_headers()
                        self.wfile.write(b'Missing URL parameter')
                
                elif self.path == '/back':
                    self.server.command_queue.put(('back',))
                    self.send_response(302)
                    self.send_header('Location', '/')
                    self.end_headers()
                
                elif self.path == '/forward':
                    self.server.command_queue.put(('forward',))
                    self.send_response(302)
                    self.send_header('Location', '/')
                    self.end_headers()
                
                elif self.path == '/reload':
                    self.server.command_queue.put(('reload',))
                    self.send_response(302)
                    self.send_header('Location', '/')
                    self.end_headers()
                
                elif self.path == '/home':
                    self.server.command_queue.put(('home',))
                    self.send_response(302)
                    self.send_header('Location', '/')
                    self.end_headers()
                
                elif self.path == '/new_tab':
                    self.server.command_queue.put(('new_tab',))
                    self.send_response(302)
                    self.send_header('Location', '/')
                    self.end_headers()
                
                elif self.path.startswith('/switch_tab?'):
                    query = self.path.split('?')[1]
                    params = urllib.parse.parse_qs(query)
                    direction = params.get('direction', [''])[0]
                    if direction in ['prev', 'next']:
                        self.server.command_queue.put(('switch_tab', direction))
                        self.send_response(302)
                        self.send_header('Location', '/')
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
                    # Default behavior: serve static files
                    super().do_GET()
        
        StreamHandler.server_directory = self.server_dir
        self.create_streaming_page()
        
        def run_server():
            with socketserver.TCPServer(("", self.server_port), StreamHandler) as httpd:
                httpd.command_queue = self.command_queue
                # Custom method to get the latest image data
                httpd.get_latest_image = lambda: self.latest_image_data
                print(f"Browser stream server running at http://localhost:{self.server_port}")
                httpd.serve_forever()
                
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        time.sleep(0.5)
            
    def process_commands(self):
        """Process commands from the web interface"""
        while not self.command_queue.empty():
            command, *args = self.command_queue.get()
            if command == 'navigate':
                url = args[0]
                self.load_url(url)
            elif command == 'back':
                self.navigate_back()
            elif command == 'forward':
                self.navigate_forward()
            elif command == 'reload':
                self.reload_page()
            elif command == 'home':
                self.navigate_home()
            elif command == 'new_tab':
                self.add_new_tab()
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
        js_code = f"""
        var activeEl = document.activeElement;
        var eventObj = new KeyboardEvent('keydown', {{
            key: '{key_escaped}',
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
    print(f"Browser stream server running at http://localhost:{browser.server_port}")
    sys.exit(app.exec_())