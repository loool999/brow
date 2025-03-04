import sys
import os
import threading
import time
import http.server
import socketserver
from datetime import datetime
from PyQt5.QtCore import QUrl, Qt, QTimer, QSize
from PyQt5.QtWidgets import (QApplication, QMainWindow, QToolBar, 
                             QLineEdit, QPushButton, QAction, QVBoxLayout, 
                             QHBoxLayout, QWidget, QTabWidget, QMenu, QStatusBar,
                             QMessageBox)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtGui import QIcon, QKeySequence, QPixmap, QImage

class WebBrowser(QMainWindow):
    
    def __init__(self):
        super().__init__()
        self.initialize_ui()
        
    def initialize_ui(self):
        # Set window properties
        self.setWindowTitle("Python Web Browser")
        self.setGeometry(100, 100, 1024, 768)
        
        # Create screenshot directory if it doesn't exist
        self.screenshot_dir = os.path.join(os.getcwd(), "screenshots")
        if not os.path.exists(self.screenshot_dir):
            os.makedirs(self.screenshot_dir)
            
        # Initialize HTTP server for serving screenshots
        self.server_port = 8000
        self.start_http_server()
        
        # Set up auto-screenshot timer
        self.auto_screenshot_enabled = True
        self.screenshot_interval = 100  # milliseconds
        self.auto_screenshot_timer = QTimer(self)
        self.auto_screenshot_timer.timeout.connect(self.take_auto_screenshot)
        self.auto_screenshot_timer.start(self.screenshot_interval)
        
        # Track latest screenshot for auto-updates
        self.latest_screenshot = None
        
        # Create tab widget to support multiple tabs
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        
        # Create actions
        self.create_actions()
        
        # Create toolbar
        self.create_toolbar()
        
        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Create first tab
        self.add_new_tab()
        
        # Set central widget
        self.setCentralWidget(self.tabs)
        self.show()
    
    def create_actions(self):
        # Back action
        self.back_action = QAction("Back", self)
        self.back_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_Left))
        self.back_action.triggered.connect(self.navigate_back)
        
        # Forward action
        self.forward_action = QAction("Forward", self)
        self.forward_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_Right))
        self.forward_action.triggered.connect(self.navigate_forward)
        
        # Reload action
        self.reload_action = QAction("Reload", self)
        self.reload_action.setShortcut(QKeySequence(Qt.Key_F5))
        self.reload_action.triggered.connect(self.reload_page)
        
        # Home action
        self.home_action = QAction("Home", self)
        self.home_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_H))
        self.home_action.triggered.connect(self.navigate_home)
        
        # New Tab action
        self.new_tab_action = QAction("New Tab", self)
        self.new_tab_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_T))
        self.new_tab_action.triggered.connect(self.add_new_tab)
        
        # Screenshot action
        self.screenshot_action = QAction("Take Screenshot", self)
        self.screenshot_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_S))
        self.screenshot_action.triggered.connect(self.take_screenshot)
        
        # Toggle Auto-Screenshot action
        self.auto_screenshot_action = QAction("Toggle Auto-Screenshot", self)
        self.auto_screenshot_action.setShortcut(QKeySequence(Qt.CTRL + Qt.Key_A))
        self.auto_screenshot_action.triggered.connect(self.toggle_auto_screenshot)
        self.auto_screenshot_action.setCheckable(True)
        self.auto_screenshot_action.setChecked(True)
        
    def create_toolbar(self):
        navigation_bar = QToolBar("Navigation")
        self.addToolBar(navigation_bar)
        
        # Add actions to toolbar
        navigation_bar.addAction(self.back_action)
        navigation_bar.addAction(self.forward_action)
        navigation_bar.addAction(self.reload_action)
        navigation_bar.addAction(self.home_action)
        navigation_bar.addAction(self.new_tab_action)
        navigation_bar.addAction(self.screenshot_action)
        navigation_bar.addAction(self.auto_screenshot_action)
        
        # Add URL bar
        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        navigation_bar.addWidget(self.url_bar)
        
        # Add Go button
        go_button = QPushButton("Go")
        go_button.clicked.connect(self.navigate_to_url)
        navigation_bar.addWidget(go_button)
    
    def add_new_tab(self, url=None):
        # Create browser frame
        browser = QWebEngineView()
        browser.page().loadProgress.connect(self.update_loading_progress)
        browser.page().loadFinished.connect(self.update_url)
        browser.page().titleChanged.connect(self.update_title)
        
        # Create tab layout
        layout = QVBoxLayout()
        layout.addWidget(browser)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create tab widget
        tab = QWidget()
        tab.setLayout(layout)
        
        # Add tab to tab widget
        index = self.tabs.addTab(tab, "New Tab")
        self.tabs.setCurrentIndex(index)
        
        # Load URL if provided
        if url:
            browser.load(QUrl(url))
        else:
            browser.load(QUrl("https://www.google.com"))
    
    def close_tab(self, index):
        if self.tabs.count() > 1:
            self.tabs.removeTab(index)
        else:
            # Don't close the last tab, just clear it
            current_browser = self.get_current_browser()
            current_browser.load(QUrl("https://www.google.com"))
    
    def get_current_browser(self):
        current_tab = self.tabs.currentWidget()
        layout = current_tab.layout()
        return layout.itemAt(0).widget()
    
    def navigate_to_url(self):
        url = self.url_bar.text()
        # Add http:// if no protocol specified
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
            self.status_bar.showMessage("Done", 2000)  # Show "Done" for 2 seconds
            
    def take_screenshot(self):
        # Get current browser widget
        current_browser = self.get_current_browser()
        
        # Create a unique filename based on timestamp and URL
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        url_part = current_browser.url().host().replace(".", "_")
        if not url_part:
            url_part = "homepage"
        filename = f"screenshot_{url_part}_{timestamp}.png"
        filepath = os.path.join(self.screenshot_dir, filename)
        
        # Take screenshot after a short delay to ensure page is fully rendered
        QTimer.singleShot(500, lambda: self._capture_screenshot(filepath))
        
    def _capture_screenshot(self, filepath):
        # Capture the current tab
        current_tab = self.tabs.currentWidget()
        pixmap = current_tab.grab()
        
        # Save the screenshot
        pixmap.save(filepath)
        
        # Update status bar
        self.status_bar.showMessage(f"Screenshot saved: {filepath}", 3000)
        
        # Update the index.html file
        self.update_screenshot_index()
        
        # Display notification with URL
        QMessageBox.information(
            self, 
            "Screenshot Captured",
            f"Screenshot saved and available at:\nhttp://localhost:{self.server_port}/{os.path.basename(filepath)}"
        )
        
    def update_screenshot_index(self):
        # Create an index.html file that lists all screenshots
        screenshots = [f for f in os.listdir(self.screenshot_dir) if f.endswith('.png') and f != "live_view.png"]
        screenshots.sort(reverse=True)  # Most recent first
        
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
            # Skip the live view screenshot
            if screenshot == "live_view.png":
                continue
                
            # Extract timestamp from filename
            timestamp_str = screenshot.split('_')[-1].split('.')[0]
            date_str = screenshot.split('_')[-2]
            formatted_time = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]} {timestamp_str[:2]}:{timestamp_str[2:4]}:{timestamp_str[4:]}"
            
            html_content += f"""
            <div class="screenshot">
                <div class="timestamp">Captured: {formatted_time}</div>
                <img src="{screenshot}" alt="Screenshot {screenshot}">
            </div>
            """
        
        html_content += """
        </body>
        </html>
        """
        
        # Write to index.html
        with open(os.path.join(self.screenshot_dir, "index.html"), "w") as f:
            f.write(html_content)
            
    def start_http_server(self):
        # Create a custom HTTP request handler
        class ScreenshotHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=self.server_directory, **kwargs)
                
            def log_message(self, format, *args):
                # Silence server logs
                pass
                
            def end_headers(self):
                # Add headers to prevent caching for live_view.png
                path = self.path.split('?')[0]  # Remove query parameters
                if path.endswith('/live_view.png'):
                    self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
                    self.send_header('Pragma', 'no-cache')
                    self.send_header('Expires', '0')
                super().end_headers()
        
        # Set the directory attribute for the handler class
        ScreenshotHandler.server_directory = self.screenshot_dir
        
        # Create initial live_view.html file
        self.update_live_view_page()
        
        # Start server in a separate thread
        def run_server():
            with socketserver.TCPServer(("", self.server_port), ScreenshotHandler) as httpd:
                print(f"Serving screenshots at http://localhost:{self.server_port}")
                print(f"Live view available at http://localhost:{self.server_port}/live_view.html")
                httpd.serve_forever()
                
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        
        # Wait a bit for the server to start
        time.sleep(0.5)

    def take_auto_screenshot(self):
        """Take automatic screenshots for live view without saving files"""
        if not self.auto_screenshot_enabled:
            return
            
        # Capture current tab
        current_tab = self.tabs.currentWidget()
        pixmap = current_tab.grab()
        
        # Create a unique filename for the live view
        live_filename = "live_view.png"
        filepath = os.path.join(self.screenshot_dir, live_filename)
        
        # Save the screenshot (overwriting previous live view)
        pixmap.save(filepath)
        
        # Update the live view page
        self.update_live_view_page()
        
        # Store as latest screenshot
        self.latest_screenshot = filepath
        
    def toggle_auto_screenshot(self):
        """Toggle automatic screenshot functionality"""
        self.auto_screenshot_enabled = not self.auto_screenshot_enabled
        
        if self.auto_screenshot_enabled:
            self.auto_screenshot_timer.start(self.screenshot_interval)
            self.status_bar.showMessage("Auto-screenshots enabled", 2000)
        else:
            self.auto_screenshot_timer.stop()
            self.status_bar.showMessage("Auto-screenshots disabled", 2000)
        
        # Update the action's checked state
        self.auto_screenshot_action.setChecked(self.auto_screenshot_enabled)
        
    def update_live_view_page(self):
        """Update the live view HTML page"""
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
                // Auto-refresh the image every 100ms
                function refreshImage() {
                    const img = document.getElementById('live-image');
                    // Add a timestamp to prevent caching
                    img.src = 'live_view.png?t=' + new Date().getTime();
                }
                
                // Set up auto-refresh
                setInterval(refreshImage, 100);
            </script>
        </head>
        <body>
            <h1>Browser Live View</h1>
            <div class="live-view">
                <img id="live-image" src="live_view.png" alt="Live Browser View">
            </div>
            <p class="refresh-note">
                <span class="auto-refresh">Auto-refreshing</span> every 100ms
            </p>
        </body>
        </html>
        """
        
        # Write to live_view.html
        with open(os.path.join(self.screenshot_dir, "live_view.html"), "w") as f:
            f.write(html_content)
            
if __name__ == "__main__":
    app = QApplication(sys.argv)
    browser = WebBrowser()
    print(f"Screenshot server running at http://localhost:{browser.server_port}")
    print(f"Live view available at http://localhost:{browser.server_port}/live_view.html")
    sys.exit(app.exec_())