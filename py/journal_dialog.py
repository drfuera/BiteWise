import gi
import json
import os
import re
import sys
from datetime import datetime
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

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
            "Atkins Diet", "Carnivore Diet", "DASH Diet", "Fruitarian Diet",
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

class AddEntryDialog(Gtk.Dialog):
    def __init__(self, journal_tab):
        super().__init__(title="Add Journal Entry", transient_for=journal_tab.get_toplevel(), modal=True)
        self.set_default_size(400, 600)
        self.journal_tab = journal_tab
        self.all_ingredients = []
        self.all_recipes = []
        self.filtered_ingredients = []
        self.filtered_recipes = []

        # Get selected date if any
        selection = journal_tab.journal_tree.get_selection()
        model, paths = selection.get_selected_rows()
        if paths:
            treeiter = model.get_iter(paths[0])
            self.selected_date = model[treeiter][0]
        else:
            self.selected_date = None

        # Load all ingredients and recipes
        self.all_ingredients = sorted(journal_tab.ingredients_data, key=lambda x: x['name'].lower())
        self.all_recipes = sorted(journal_tab.recipes_data, key=lambda x: x['name'].lower())
        self.filtered_ingredients = self.all_ingredients.copy()
        self.filtered_recipes = self.all_recipes.copy()

        # Create widgets
        self.filter_entry = Gtk.Entry(placeholder_text="Filter ingredients/recipes...")
        self.filter_entry.connect("changed", self.on_filter_changed)

        # Ingredients list
        self.ingredients_list = Gtk.ListStore(str)
        self.ingredients_view = Gtk.TreeView(model=self.ingredients_list)
        self.ingredients_view.set_headers_visible(False)
        self.ingredients_view.set_size_request(-1, 150)  # 8 rows * ~18px per row
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Ingredients", renderer, text=0)
        self.ingredients_view.append_column(column)
        self.ingredients_selection = self.ingredients_view.get_selection()
        self.ingredients_selection.connect("changed", self.on_ingredient_selected)

        # Recipes list
        self.recipes_list = Gtk.ListStore(str)
        self.recipes_view = Gtk.TreeView(model=self.recipes_list)
        self.recipes_view.set_headers_visible(False)
        self.recipes_view.set_size_request(-1, 150)  # 8 rows * ~18px per row
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Recipes", renderer, text=0)
        self.recipes_view.append_column(column)
        self.recipes_selection = self.recipes_view.get_selection()
        self.recipes_selection.connect("changed", self.on_recipe_selected)

        self.gram_entry = Gtk.Entry(placeholder_text="Grams", width_chars=7)
        self.gram_entry.connect("changed", self._on_numeric_entry_changed)
        self.gram_entry.connect("activate", self.on_add_clicked)  # Connect Enter key to add action

        self.weight_entry = Gtk.Entry(placeholder_text="My kg.hg", width_chars=10)
        self.weight_entry.connect("changed", self._on_numeric_entry_changed)
        if journal_tab.last_entered_weight:
            self.weight_entry.set_text(journal_tab.last_entered_weight)

        self.pts_check = Gtk.CheckButton(label="Pts.")
        self.pts_check.set_sensitive(False)
        self.pts_check.connect("toggled", self.on_pts_check_toggled)

        self.add_to_selected_check = Gtk.CheckButton(label="Add to date")
        self.add_to_selected_check.set_sensitive(self.selected_date is not None)

        # Layout
        content_area = self.get_content_area()
        content_area.set_spacing(10)
        content_area.set_margin_top(10)
        content_area.set_margin_bottom(10)
        content_area.set_margin_start(10)
        content_area.set_margin_end(10)

        # Main frame with title
        main_frame = Gtk.Frame(label="Add Journal Entry")
        content_area.pack_start(main_frame, True, True, 0)

        frame_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=10)
        main_frame.add(frame_box)

        # Filter entry
        frame_box.pack_start(self.filter_entry, False, False, 0)

        # Lists container
        lists_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        frame_box.pack_start(lists_box, True, True, 0)

        # Ingredients scrolled window
        ingredients_scrolled = Gtk.ScrolledWindow()
        ingredients_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        ingredients_scrolled.add(self.ingredients_view)
        lists_box.pack_start(ingredients_scrolled, True, True, 0)

        # Recipes scrolled window
        recipes_scrolled = Gtk.ScrolledWindow()
        recipes_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        recipes_scrolled.add(self.recipes_view)
        lists_box.pack_start(recipes_scrolled, True, True, 0)

        # Grams row with checkboxes right-aligned
        grams_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        frame_box.pack_start(grams_box, False, False, 0)
        grams_box.pack_start(self.gram_entry, False, False, 0)
        
        # Spacer to push checkboxes to the right
        spacer = Gtk.Box()
        grams_box.pack_start(spacer, True, True, 0)

        # Checkboxes box
        checkboxes_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        checkboxes_box.pack_start(self.pts_check, False, False, 0)
        checkboxes_box.pack_start(self.add_to_selected_check, False, False, 0)
        grams_box.pack_start(checkboxes_box, False, False, 0)

        # Weight entry with fixed width, right-aligned
        weight_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        weight_box.set_halign(Gtk.Align.END)
        weight_box.pack_start(Gtk.Box(), True, True, 0)  # Spacer to push entry to the right
        weight_box.pack_start(self.weight_entry, False, False, 0)
        frame_box.pack_start(weight_box, False, False, 0)

        # Buttons
        button_box = Gtk.Box(spacing=10)
        frame_box.pack_start(button_box, False, False, 0)

        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", lambda b: self.destroy())
        button_box.pack_start(cancel_button, False, False, 0)

        button_box.pack_start(Gtk.Box(), True, True, 0)  # Spacer

        add_button = Gtk.Button(label="Add")
        add_button.connect("clicked", self.on_add_clicked)
        button_box.pack_start(add_button, False, False, 0)

        # Populate lists
        self.update_lists()
        self.show_all()

    def update_lists(self):
        self.ingredients_list.clear()
        for item in self.filtered_ingredients:
            self.ingredients_list.append([item['name']])

        self.recipes_list.clear()
        for item in self.filtered_recipes:
            self.recipes_list.append([item['name']])

    def on_filter_changed(self, entry):
        filter_text = entry.get_text().lower()
        
        if not filter_text:
            self.filtered_ingredients = self.all_ingredients.copy()
            self.filtered_recipes = self.all_recipes.copy()
        else:
            self.filtered_ingredients = [
                item for item in self.all_ingredients 
                if filter_text in item['name'].lower()
            ]
            self.filtered_recipes = [
                item for item in self.all_recipes 
                if filter_text in item['name'].lower()
            ]
        
        self.update_lists()
        self.ingredients_selection.unselect_all()
        self.recipes_selection.unselect_all()

    def on_ingredient_selected(self, selection):
        model, treeiter = selection.get_selected()
        if treeiter:
            self.recipes_selection.unselect_all()
            self.pts_check.set_sensitive(False)
            if self.pts_check.get_active():
                self.pts_check.set_active(False)
                self.gram_entry.set_placeholder_text("Grams")

    def on_recipe_selected(self, selection):
        model, treeiter = selection.get_selected()
        if treeiter:
            self.ingredients_selection.unselect_all()
            self.pts_check.set_sensitive(True)

    def on_pts_check_toggled(self, button):
        if button.get_active():
            self.gram_entry.set_placeholder_text("Pts.")
        else:
            self.gram_entry.set_placeholder_text("Grams")

    def _on_numeric_entry_changed(self, entry):
        text = entry.get_text()
        if not text or re.match(r'^[0-9]*[,.]?[0-9]*$', text):
            return
        pos = entry.get_position()
        filtered = ''.join(c for c in text if c in '0123456789,.' and 
                          (c != ',' or text.count(',') <= 1) and 
                          (c != '.' or text.count('.') <= 1))
        entry.set_text(filtered)
        entry.set_position(min(pos, len(filtered)))

    def on_add_clicked(self, widget):
        ingredient_name = None
        recipe_name = None
        gram_text = self.gram_entry.get_text().strip()
        weight_text = self.weight_entry.get_text().strip()
        pts_active = self.pts_check.get_active()
        add_to_selected = self.add_to_selected_check.get_active()

        # Get selected ingredient if any
        ing_model, ing_iter = self.ingredients_selection.get_selected()
        if ing_iter:
            ingredient_name = ing_model.get_value(ing_iter, 0)

        # Get selected recipe if any
        rec_model, rec_iter = self.recipes_selection.get_selected()
        if rec_iter:
            recipe_name = rec_model.get_value(rec_iter, 0)

        if add_to_selected and self.selected_date:
            date = self.selected_date
            timestamp = f"{date} 23:59:59"
        else:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            date = datetime.now().strftime("%Y-%m-%d")

        if self.journal_tab.add_entry(ingredient_name, recipe_name, gram_text, weight_text, pts_active, date, timestamp):
            # Clear inputs after successful add, except weight
            self.gram_entry.set_text('')
            self.pts_check.set_active(False)
            self.filter_entry.set_text('')  # Clear search field
            self.on_filter_changed(self.filter_entry)  # Update lists
            self.ingredients_selection.unselect_all()
            self.recipes_selection.unselect_all()
            self.filter_entry.grab_focus()  # Set focus to search field

    def _show_error(self, message):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=message
        )
        dialog.run()
        dialog.destroy(
