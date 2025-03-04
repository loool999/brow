import sys
from PyQt5.QtCore import QUrl, Qt
from PyQt5.QtWidgets import (QApplication, QMainWindow, QToolBar, 
                             QLineEdit, QPushButton, QAction, QVBoxLayout, 
                             QHBoxLayout, QWidget, QTabWidget, QMenu, QStatusBar)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtGui import QIcon, QKeySequence

class WebBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initialize_ui()
        
    def initialize_ui(self):
        # Set window properties
        self.setWindowTitle("Python Web Browser")
        self.setGeometry(100, 100, 1024, 768)
        
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
        
    def create_toolbar(self):
        navigation_bar = QToolBar("Navigation")
        self.addToolBar(navigation_bar)
        
        # Add actions to toolbar
        navigation_bar.addAction(self.back_action)
        navigation_bar.addAction(self.forward_action)
        navigation_bar.addAction(self.reload_action)
        navigation_bar.addAction(self.home_action)
        navigation_bar.addAction(self.new_tab_action)
        
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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    browser = WebBrowser()
    sys.exit(app.exec_())