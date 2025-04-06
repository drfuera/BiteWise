import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, Pango
import webbrowser
import os
from pathlib import Path

class AboutTab(Gtk.Box):
    def __init__(self, window_width, window_height):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.set_border_width(20)
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.CENTER)
        
        # Main container with shadow effect and titled border
        main_frame = Gtk.Frame()
        main_frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        main_frame.set_label(" About ")  # Title in the border
        main_frame.set_label_align(0.5, 0.5)  # Center the title
        main_frame.set_size_request(600, -1)
        self.pack_start(main_frame, False, False, 0)
        
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        main_box.set_border_width(20)
        main_box.set_margin_top(10)  # Extra margin to compensate for title
        main_frame.add(main_box)
        
        # Application logo
        logo_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        logo_box.set_halign(Gtk.Align.CENTER)
        
        try:
            icon_path = Path(__file__).parent / "../db/icon.png"
            if icon_path.exists():
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(str(icon_path), 80, 80)  # Larger icon
                image = Gtk.Image.new_from_pixbuf(pixbuf)
                logo_box.pack_start(image, False, False, 0)
        except Exception as e:
            print(f"Error loading icon: {e}")
        
        # Application title - made significantly larger
        title_label = Gtk.Label()
        title_label.set_markup("<span size='400%' weight='ultrabold'>BiteWise</span>")  # 300% larger than default
        title_label.set_margin_bottom(0)
        logo_box.pack_start(title_label, False, False, 15)  # Increased spacing
        main_box.pack_start(logo_box, False, False, 0)
        
        # Description
        desc_label = Gtk.Label()
        desc_label.set_markup(
            "<span size='large'>A comprehensive nutrition and recipe management application.</span>\n\n"
            "Track your meals, analyze nutrition, manage recipes,\n"
            "and monitor your dietary goals all in one place."
        )
        desc_label.set_line_wrap(True)
        desc_label.set_justify(Gtk.Justification.CENTER)
        desc_label.set_margin_bottom(20)
        main_box.pack_start(desc_label, False, False, 0)
        
        # Info grid
        grid = Gtk.Grid()
        grid.set_column_spacing(10)
        grid.set_row_spacing(10)
        grid.set_margin_bottom(20)
        grid.set_halign(Gtk.Align.CENTER)
        
        # Version
        self._add_grid_row(grid, 0, "Version:", "1.0.0")
        # Author
        self._add_grid_row(grid, 1, "Author:", "Your Name")
        # Email
        email_label = self._add_grid_row(grid, 2, "Contact:", "your.email@example.com")
        email_label.connect("activate-link", self._on_email_clicked)
        # GitHub
        github_label = self._add_grid_row(grid, 3, "GitHub:", "github.com/yourusername/bitewise")
        github_label.connect("activate-link", self._on_github_clicked)
        
        main_box.pack_start(grid, False, False, 0)
        
        # License
        license_label = Gtk.Label()
        license_label.set_markup(
            "<span size='small'>© 2023 BiteWise - Licensed under MIT License</span>"
        )
        license_label.set_margin_top(20)
        main_box.pack_start(license_label, False, False, 0)
        
        # Show all
        self.show_all()
    
    def _add_grid_row(self, grid, row, label_text, value_text):
        label = Gtk.Label(label=label_text)
        label.set_halign(Gtk.Align.END)
        label.set_margin_right(10)
        grid.attach(label, 0, row, 1, 1)
        
        if value_text.startswith(('http://', 'https://', 'mailto:')):
            value_label = Gtk.Label()
            value_label.set_markup(f"<a href='{value_text}'>{value_text}</a>")
            value_label.set_halign(Gtk.Align.START)
        else:
            value_label = Gtk.Label(label=value_text)
            value_label.set_halign(Gtk.Align.START)
        
        grid.attach(value_label, 1, row, 1, 1)
        return value_label
    
    def _on_email_clicked(self, label, uri):
        webbrowser.open(f"mailto:{uri}")
        return True
    
    def _on_github_clicked(self, label, uri):
        webbrowser.open(f"https://{uri}")
        return True
