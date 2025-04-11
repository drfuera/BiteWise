import gi
import json
import os
import sys
from datetime import datetime
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

class DietSettingsDialog(Gtk.Dialog):
    def __init__(self, parent):
        super().__init__(title="Diet Settings", transient_for=parent, modal=True)
        self.set_default_size(250, 150)
        self.db_dir = self._get_db_dir()
        self.existing_settings = self._load_settings()
        self._setup_ui()

    def _get_db_dir(self):
        if 'APPIMAGE' in os.environ:
            base_dir = os.path.dirname(os.environ['APPIMAGE'])
        elif getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        db_dir = os.path.join(base_dir, 'db')
        os.makedirs(db_dir, exist_ok=True)
        return db_dir

    def _load_settings(self):
        try:
            with open(os.path.join(self.db_dir, 'diet.json'), 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading diet settings: {e}")
            return {}

    def _setup_ui(self):
        content_area = self.get_content_area()
        content_area.set_spacing(10)
        content_area.set_margin_top(10)
        content_area.set_margin_bottom(10)
        content_area.set_margin_start(10)
        content_area.set_margin_end(10)

        # BMI Frame
        bmi_frame = Gtk.Frame(label="BMI Settings")
        bmi_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5, margin=10)
        
        self.dob_entry = Gtk.Entry(placeholder_text="Birth date (YYYYMMDD)")
        self.dob_entry.set_text(self.existing_settings.get('date_of_birth', ''))
        bmi_box.pack_start(self.dob_entry, False, False, 0)

        self.height_entry = Gtk.Entry(placeholder_text="Height in cm", input_purpose=Gtk.InputPurpose.NUMBER)
        self.height_entry.set_text(str(self.existing_settings.get('height_cm', '')))
        bmi_box.pack_start(self.height_entry, False, False, 0)

        self.gender_combo = Gtk.ComboBoxText()
        for gender in ["Male", "Female"]:
            self.gender_combo.append_text(gender)
        current_gender = self.existing_settings.get('gender', 'Male')
        self.gender_combo.set_active(0 if current_gender == "Male" else 1)
        bmi_box.pack_start(self.gender_combo, False, False, 0)

        bmi_frame.add(bmi_box)
        content_area.add(bmi_frame)

        # Diet Frame
        diet_frame = Gtk.Frame(label="Diet Settings")
        diet_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5, margin=10)
        
        diets = ["None"] + sorted([
            "Atkins Diet", "Carnivore Diet", "DASH Diet", "Flexitarian Diet", "Fruitarian Diet",
            "High Protein Diet", "Ketogenic Diet", "LCHF", "Mediterranean Diet", "Military Diet",
            "Paleo Diet", "Pescatarian Diet", "Raw Food Diet", "Ray Kurzweil Diet", "Scandinavian Diet",
            "Vegan Diet", "WHO Guidelines", "Zone Diet"
        ])
        
        self.diet_combo = Gtk.ComboBoxText()
        for diet in diets:
            self.diet_combo.append_text(diet)
        
        current_diet = self.existing_settings.get('diet', 'None')
        if not current_diet or current_diet not in diets:
            current_diet = 'None'
        self.diet_combo.set_active(diets.index(current_diet))
        
        diet_box.pack_start(self.diet_combo, False, False, 0)
        
        diet_frame.add(diet_box)
        content_area.add(diet_frame)

        # Buttons
        button_box = Gtk.Box(spacing=10)
        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", lambda w: self.destroy())
        button_box.pack_start(cancel_button, False, False, 0)
        
        button_box.pack_start(Gtk.Box(), True, True, 0)
        
        save_button = Gtk.Button(label="Save")
        save_button.connect("clicked", self.on_save_clicked)
        button_box.pack_end(save_button, False, False, 0)
        
        content_area.add(button_box)
        self.show_all()

    def on_save_clicked(self, widget):
        dob = self.dob_entry.get_text().strip()
        height = self.height_entry.get_text().strip()
        gender = self.gender_combo.get_active_text()
        diet = self.diet_combo.get_active_text()

        if not (dob.isdigit() and len(dob) == 8):
            self._show_error("Enter a valid birth date (YYYYMMDD)")
            return
        try:
            datetime.strptime(dob, "%Y%m%d")
        except ValueError:
            self._show_error("Invalid birth date")
            return

        if not height.isdigit():
            self._show_error("Enter a valid height in cm (whole number)")
            return

        data = {
            'date_of_birth': dob,
            'height_cm': int(height),
            'gender': gender,
            'diet': diet if diet != "None" else ""
        }
        
        try:
            with open(os.path.join(self.db_dir, 'diet.json'), 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            parent = self.get_transient_for()
            if hasattr(parent, '_refresh_journal_view'):
                parent._refresh_journal_view()
            self.destroy()
        except Exception as e:
            self._show_error(f"Error saving diet settings: {e}")

    def _show_error(self, message):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=message
        )
        dialog.run()
        dialog.destroy()
