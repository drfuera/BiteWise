import os
import sys
import subprocess
from pathlib import Path
import time
import threading
import gi
gi.require_version('Gtk', '3.0')

def ensure_db_directory():
    if 'APPIMAGE' in os.environ:
        base_dir = os.path.dirname(os.environ['APPIMAGE'])
    elif getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    db_path = os.path.join(base_dir, 'db')
    
    if not os.path.exists(db_path):
        try:
            os.makedirs(db_path)
            print(f"Created db directory at: {db_path}")
        except Exception as e:
            print(f"Error creating db directory: {e}")
            return False
    return True

class SplashScreen:
    def __init__(self):
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk, GLib
        
        self.window = Gtk.Window(Gtk.WindowType.POPUP)
        self.window.set_default_size(400, 200)
        self.window.set_position(Gtk.WindowPosition.CENTER)
        self.window.set_decorated(False)
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        box.set_margin_start(20)
        box.set_margin_end(20)
        self.window.add(box)
        
        self.label = Gtk.Label(label="Initializing BiteWise...")
        self.label.set_halign(Gtk.Align.CENTER)
        box.pack_start(self.label, True, True, 0)
        
        self.progress = Gtk.ProgressBar()
        box.pack_start(self.progress, False, True, 0)
        
        self.status_label = Gtk.Label(label="Checking dependencies...")
        self.status_label.set_halign(Gtk.Align.CENTER)
        box.pack_start(self.status_label, True, True, 0)
        
        self.window.show_all()
        
        self.gtk = Gtk
        self.glib = GLib
    
    def update(self, text, progress=None):
        def _update():
            self.label.set_text(text)
            if progress is not None:
                self.progress.set_fraction(progress)
            self.status_label.set_text(f"Installing: {text}" if progress is not None else text)
            while self.gtk.events_pending():
                self.gtk.main_iteration()
        
        self.glib.idle_add(_update)
    
    def close(self):
        self.glib.idle_add(self.window.destroy)

def install_dependencies():
    required_packages = {
        'PyGObject': 'gi',
        'pycairo': 'cairo',
        'Pillow': 'PIL',
        'requests': 'requests'
    }
    
    missing = [pkg for pkg, mod in required_packages.items() 
              if not is_module_available(mod)]
    
    if not missing:
        return True
    
    splash = SplashScreen()
    splash.update("Preparing to install dependencies...", 0)
    
    total = len(missing)
    installed = 0
    
    def install_thread():
        nonlocal installed
        try:
            for i, pkg in enumerate(missing, 1):
                splash.update(f"Installing {pkg}...", i/total)
                
                cmd = [sys.executable, "-m", "pip", "install", "--user", pkg]
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                while True:
                    output = process.stdout.readline()
                    if process.poll() is not None and output == b'':
                        break
                    if output:
                        pass
                
                if process.returncode != 0:
                    splash.update(f"Failed to install {pkg}", 1.0)
                    time.sleep(2)
                    splash.close()
                    return False
                
                installed += 1
            
            splash.update("Dependencies installed successfully!", 1.0)
            time.sleep(1)
            splash.close()
            return True
        except Exception as e:
            splash.update(f"Installation error: {str(e)}", 1.0)
            time.sleep(3)
            splash.close()
            return False
    
    thread = threading.Thread(target=install_thread)
    thread.daemon = True
    thread.start()
    
    from gi.repository import Gtk
    while thread.is_alive():
        Gtk.main_iteration_do(False)
    
    thread.join()
    return installed == total

def is_module_available(module_name):
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False

if not ensure_db_directory():
    print("Failed to create db directory. The application may not work correctly.")
    sys.exit(1)

if not install_dependencies():
    print("Failed to install required dependencies. Please install them manually.")
    sys.exit(1)

from gi.repository import Gtk, Pango, Gdk
from py.recipes_tab import RecipesTab
from py.ingredients_tab import IngredientsTab
from py.journal_tab import JournalTab
from py.weight_tab import WeightStatsTab
from py.bmr_tab import BMRStatsTab
from py.macro_tab import MacroBreakdownTab
from py.costs_tab import CostsTab
from py.youtube_tab import YouTubeTab
from py.about_tab import AboutTab
from py.nutrition_tab import NutritionTab
from py.timeline_tab import TimelineTab

class RecipeManager(Gtk.Window):
    def __init__(self):
        super().__init__(title="BiteWise")
        self.set_default_size(1200, 780)
        self._set_app_icon()

        self.notebook = Gtk.Notebook()
        self.add(self.notebook)

        self.journal_tab = JournalTab(1200, 780)
        self.recipes_tab = RecipesTab(1200, 780, self)
        self.weight_tab = WeightStatsTab(1200, 780)
        self.bmr_tab = BMRStatsTab(1200, 780)
        self.macro_tab = MacroBreakdownTab(1200, 780)
        
        ingredients_tab = IngredientsTab(1200, 780, self.recipes_tab, self.journal_tab)
        self.journal_tab.set_weight_tab(self.weight_tab)
        self.journal_tab.set_bmr_tab(self.bmr_tab)
        self.journal_tab.set_macro_tab(self.macro_tab)

        tabs = [
            (self.journal_tab, "Journal"),
            (self.recipes_tab, "Recipes"),
            (ingredients_tab, "Ingredients"),
            (self.weight_tab, "Weight"),
            (self.bmr_tab, "BMR & Kcal"),
            (self.macro_tab, "Macro"),
            (TimelineTab(1200, 780), "Timeline"),
            (NutritionTab(1200, 780), "Nutrition"),
            (CostsTab(1200, 780), "Costs"),
            (YouTubeTab(1200, 780), "Video Cookbook"),
            (AboutTab(1200, 780), "About")
        ]

        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"label { font-size: 12px; font-weight: bold; } label:focus, *:focus { outline: none; }")

        for content, label in tabs:
            scrolled = Gtk.ScrolledWindow()
            scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scrolled.add(content)
            
            tab_label = Gtk.Label(label=label)
            tab_label.set_margin_start(15)
            tab_label.set_margin_end(15)
            tab_label.set_margin_top(8)
            tab_label.set_margin_bottom(8)
            tab_label.get_style_context().add_provider(
                css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
            self.notebook.append_page(scrolled, tab_label)

        self.connect("key-press-event", self.on_key_press)
        
        self.show_all()

    def _set_app_icon(self):
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        
        icon_path = os.path.join(base_dir, 'db', 'icon.png')
        if os.path.exists(icon_path):
            self.set_icon_from_file(icon_path)

    def on_key_press(self, widget, event):
        if (event.state & Gdk.ModifierType.MOD1_MASK) and not (event.state & Gdk.ModifierType.CONTROL_MASK):
            if Gdk.KEY_1 <= event.keyval <= Gdk.KEY_9:
                tab_index = event.keyval - Gdk.KEY_1
                if tab_index < self.notebook.get_n_pages():
                    self.notebook.set_current_page(tab_index)
                return True
            elif event.keyval == Gdk.KEY_0:
                self.notebook.set_current_page(self.notebook.get_n_pages() - 1)
                return True

        ctrl_pressed = event.state & Gdk.ModifierType.CONTROL_MASK
        shift_pressed = event.state & Gdk.ModifierType.SHIFT_MASK
        
        if ctrl_pressed and (event.keyval == Gdk.KEY_Tab or event.keyval == Gdk.KEY_ISO_Left_Tab):
            current = self.notebook.get_current_page()
            n_pages = self.notebook.get_n_pages()
            
            if shift_pressed or event.keyval == Gdk.KEY_ISO_Left_Tab:
                new_page = (current - 1) % n_pages
            else:
                new_page = (current + 1) % n_pages
            
            self.notebook.set_current_page(new_page)
            return True

        return False

    def on_recipes_changed(self):
        self.journal_tab.reload_recipes()

if __name__ == "__main__":
    win = RecipeManager()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()
