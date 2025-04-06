import gi
import json
import re
import os
from datetime import datetime
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk
from .diet_guidelines import get_diet_colors, calculate_bmr, calculate_remaining
from .journal_dialog import DietSettingsDialog

class JournalTab(Gtk.Box):
    def __init__(self, window_width, window_height):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.set_border_width(10)
        
        self.db_dir = os.path.join(os.path.dirname(__file__), '../db')
        self._load_data()
        self._setup_ui()

    def _load_data(self):
        self.ingredients_data = []
        self.recipes_data = []
        self.journal_data = []
        self.diet_settings = {}
        self.weight_tab = self.bmr_tab = self.macro_tab = None

        files = {
            'ingredients': ('ingredients.json', 'ingredients'),
            'recipes': ('recipes.json', 'recipes'),
            'journal': ('journal.json', 'entries'),
            'diet': ('diet.json', None)
        }

        for key, (filename, data_key) in files.items():
            try:
                path = os.path.join(self.db_dir, filename)
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data_key:
                        setattr(self, f"{key}_data", data.get(data_key, []))
                    else:
                        self.diet_settings = data
            except Exception as e:
                print(f"Error loading {filename}: {e}")

        if self.journal_data:
            for entry in self.journal_data:
                if 'timestamp' not in entry and 'date' in entry:
                    entry['timestamp'] = f"{entry['date']} 00:00:00"
            self.last_weight = str(self.journal_data[-1].get('weight', '')) if self.journal_data else ''
        else:
            self.last_weight = ''

    def _setup_ui(self):
        # Top controls box
        top_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.pack_start(top_box, False, False, 0)

        self.diet_settings_button = Gtk.Button(label="Diet settings")
        self.diet_settings_button.connect("clicked", self.on_diet_settings_clicked)
        top_box.pack_start(self.diet_settings_button, False, False, 0)

        top_box.pack_start(Gtk.Box(), True, True, 0)

        self.ingredient_combo = Gtk.ComboBoxText()
        self._populate_ingredient_combo()
        top_box.pack_start(self.ingredient_combo, False, False, 0)

        self.recipe_combo = Gtk.ComboBoxText()
        for recipe in sorted(self.recipes_data, key=lambda x: x['name'].lower()):
            self.recipe_combo.append_text(recipe['name'])
        top_box.pack_start(self.recipe_combo, False, False, 0)

        self.gram_entry = Gtk.Entry(placeholder_text="Grams", width_chars=5)
        self.gram_entry.connect("changed", self._on_numeric_entry_changed)
        top_box.pack_start(self.gram_entry, False, False, 0)

        self.add_button = Gtk.Button(label="Add to journal")
        self.add_button.connect("clicked", self.on_add_to_journal_clicked)
        top_box.pack_start(self.add_button, False, False, 0)

        # Middle controls box
        middle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.pack_start(middle_box, False, False, 0)

        self.weight_entry = Gtk.Entry(placeholder_text="My kg.hg", width_chars=7)
        self.weight_entry.connect("changed", self._on_numeric_entry_changed)
        if self.last_weight:
            self.weight_entry.set_text(self.last_weight)
        middle_box.pack_start(self.weight_entry, False, False, 0)

        middle_box.pack_start(Gtk.Box(), True, True, 0)

        self.add_to_selected_check = Gtk.CheckButton(label="Add to selected date")
        middle_box.pack_start(self.add_to_selected_check, False, False, 0)

        # Journal table
        columns = [
            ("Date", 0.12), ("Grams", 0.08), ("Calories", 0.10), ("Carbs", 0.10),
            ("Sugar", 0.10), ("Fat", 0.10), ("Protein", 0.10), ("Fiber", 0.10),
            ("Salt", 0.10), ("Cost", 0.10)
        ]
        self.journal_store = Gtk.ListStore(*([str] + [float]*9))
        self.journal_tree = Gtk.TreeView(model=self.journal_store)
        self.journal_tree.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)
        self.create_columns(self.journal_tree, columns, sortable=True)
        self.journal_store.set_sort_column_id(0, Gtk.SortType.DESCENDING)

        self.journal_tree.set_has_tooltip(True)
        self.journal_tree.connect("query-tooltip", self.on_query_tooltip)
        self.journal_tree.connect("row-activated", self.on_row_activated)
        self.journal_tree.connect("key-press-event", self.on_key_press)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.add(self.journal_tree)
        
        frame = Gtk.Frame()
        frame.add(scrolled_window)
        self.pack_start(frame, True, True, 0)

        self._populate_journal_store()
        self.ingredient_combo.connect("changed", lambda c: self.recipe_combo.set_active(-1) if c.get_active_text() else None)
        self.recipe_combo.connect("changed", lambda c: self.ingredient_combo.set_active(-1) if c.get_active_text() else None)

    def on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Delete:
            self.remove_selected_entries()
            return True
        return False

    def remove_selected_entries(self):
        selection = self.journal_tree.get_selection()
        model, paths = selection.get_selected_rows()
        
        if not paths:
            return

        confirm_dialog = Gtk.MessageDialog(
            transient_for=self.get_toplevel(),
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Remove {len(paths)} selected entries?"
        )
        
        response = confirm_dialog.run()
        confirm_dialog.destroy()
        
        if response == Gtk.ResponseType.YES:
            dates_to_update = set()
            paths.sort(reverse=True)
            
            for path in paths:
                treeiter = model.get_iter(path)
                date = model[treeiter][0]
                dates_to_update.add(date)
                self.journal_data[:] = [e for e in self.journal_data if e['date'] != date]
            
            self._save_journal()
            self._refresh_journal_view()
            
            for tab in [self.weight_tab, self.bmr_tab, self.macro_tab]:
                if tab and hasattr(tab, 'update_plot'):
                    tab.update_plot()
                if tab and hasattr(tab, 'update_bmr_plot'):
                    tab.update_bmr_plot()
                if tab and hasattr(tab, 'update_charts'):
                    tab.update_charts()
        
        selection.unselect_all()

    def create_columns(self, treeview, columns, sortable=False):
        treeview.proportions = []
        format_map = {
            1: "{:.1f}", 2: "{:.1f}", 3: "{:.1f}", 4: "{:.1f}",
            5: "{:.1f}", 6: "{:.1f}", 7: "{:.1f}", 8: "{:.1f}", 9: "{:.2f}"
        }

        for idx, (col_name, proportion) in enumerate(columns):
            renderer = Gtk.CellRendererText(xalign=1.0 if idx else 0.0)
            col = Gtk.TreeViewColumn(col_name, renderer)
            col.set_cell_data_func(renderer, self.cell_data_func, idx)
            if idx:
                col.set_alignment(1.0)
            col.set_resizable(True)
            
            if sortable:
                col.set_sort_column_id(idx)
                col.set_clickable(True)
                treeview.get_model().set_sort_func(idx, self._sort_func, idx)
            
            treeview.append_column(col)
            treeview.proportions.append(proportion)
        
        treeview.connect("size-allocate", self._update_column_widths)

    def set_weight_tab(self, weight_tab):
        self.weight_tab = weight_tab

    def set_bmr_tab(self, bmr_tab):
        self.bmr_tab = bmr_tab

    def set_macro_tab(self, macro_tab):
        self.macro_tab = macro_tab

    def reload_ingredients(self):
        try:
            with open(os.path.join(self.db_dir, 'ingredients.json'), 'r', encoding='utf-8') as f:
                self.ingredients_data = json.load(f).get('ingredients', [])
            self._populate_ingredient_combo()
        except Exception as e:
            print(f"Error reloading ingredients: {e}")

    def reload_recipes(self):
        try:
            with open(os.path.join(self.db_dir, 'recipes.json'), 'r', encoding='utf-8') as f:
                self.recipes_data = json.load(f).get('recipes', [])
            self.recipe_combo.remove_all()
            for recipe in sorted(self.recipes_data, key=lambda x: x['name'].lower()):
                self.recipe_combo.append_text(recipe['name'])
        except Exception as e:
            print(f"Error reloading recipes: {e}")

    def reload_journal(self):
        try:
            with open(os.path.join(self.db_dir, 'journal.json'), 'r', encoding='utf-8') as f:
                self.journal_data = json.load(f).get('entries', [])
                for entry in self.journal_data:
                    if 'timestamp' not in entry and 'date' in entry:
                        entry['timestamp'] = f"{entry['date']} 00:00:00"
                self.last_weight = str(self.journal_data[-1].get('weight', '')) if self.journal_data else ''
            
            self._populate_journal_store()
            if hasattr(self, 'weight_entry') and self.weight_entry and self.last_weight:
                self.weight_entry.set_text(self.last_weight)
            
            if self.weight_tab and hasattr(self.weight_tab, 'update_plot'):
                self.weight_tab.update_plot()
            if self.bmr_tab and hasattr(self.bmr_tab, 'update_bmr_plot'):
                self.bmr_tab.update_bmr_plot()
            if self.macro_tab and hasattr(self.macro_tab, 'update_charts'):
                self.macro_tab.update_charts()
        except Exception as e:
            print(f"Error reloading journal: {e}")

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

    def _populate_ingredient_combo(self):
        self.ingredient_combo.remove_all()
        for ingredient in sorted(self.ingredients_data, key=lambda x: x['name'].lower()):
            self.ingredient_combo.append_text(ingredient['name'])

    def on_diet_settings_clicked(self, widget):
        dialog = DietSettingsDialog(self.get_toplevel())
        response = dialog.run()
        dialog.destroy()
        
        try:
            with open(os.path.join(self.db_dir, 'diet.json'), 'r', encoding='utf-8') as f:
                self.diet_settings = json.load(f)
            self._refresh_journal_view()
            self.journal_tree.queue_draw()
        except Exception as e:
            print(f"Error reloading diet settings: {e}")

    def on_row_activated(self, treeview, path, column):
        selected_date = self.journal_store[path][0]
        
        self.detail_dialog = Gtk.Dialog(
            title=f"Journal Entries for {selected_date}",
            transient_for=self.get_toplevel(),
            modal=True
        )
        self.detail_dialog.set_default_size(800, 600)
        self.detail_dialog.set_border_width(0)
        
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0, margin=10)
        self.detail_dialog.get_content_area().pack_start(content_box, True, True, 0)
        
        frame = Gtk.Frame(margin_top=0, margin_bottom=0)
        content_box.pack_start(frame, True, True, 0)
        
        self.detail_store = Gtk.ListStore(str, int, float, float, float, float, float, float, float, float)
        self.selected_date_entries = sorted(
            [e for e in self.journal_data if e['date'] == selected_date],
            key=lambda x: x['timestamp'], reverse=True
        )
        
        total_kcal = sum(e.get('kcal', 0) for e in self.selected_date_entries)
        bmr = None
        
        if all(k in self.diet_settings for k in ['date_of_birth', 'height_cm', 'gender']):
            try:
                dob = self.diet_settings['date_of_birth']
                height = self.diet_settings['height_cm']
                gender = self.diet_settings['gender']
                weight = self.selected_date_entries[-1].get('weight', 0) if self.selected_date_entries else 0
                if weight > 0:
                    birth_year = int(dob[:4])
                    age = datetime.now().year - birth_year
                    bmr = calculate_bmr(gender, weight, height, age)
            except Exception as e:
                print(f"BMR calculation error: {e}")
        
        for entry in self.selected_date_entries:
            self.detail_store.append([
                entry.get('ate', 'N/A'),
                entry.get('gram', 0),
                entry.get('kcal', 0),
                entry.get('carbs', 0),
                entry.get('sugar', 0),
                entry.get('fat', 0),
                entry.get('protein', 0),
                entry.get('fiber', 0),
                entry.get('salt', 0),
                entry.get('cost', 0)
            ])
        
        self.detail_tree = Gtk.TreeView(model=self.detail_store)
        self.detail_tree.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)
        self.detail_tree.set_margin_top(0)
        self.detail_tree.set_margin_bottom(0)
        
        columns = [
            ("Item", 0.4), ("Grams", 0.07), ("Calories", 0.08), ("Carbs", 0.08),
            ("Sugar", 0.08), ("Fat", 0.06), ("Protein", 0.08), ("Fiber", 0.07),
            ("Salt", 0.06), ("Cost", 0.02)
        ]
        
        self.detail_tree.proportions = []
        for idx, (col_name, proportion) in enumerate(columns):
            renderer = Gtk.CellRendererText(xalign=1.0 if idx else 0.0)
            col = Gtk.TreeViewColumn(col_name, renderer)
            col.set_cell_data_func(renderer, self.detail_cell_data_func, (idx, total_kcal, bmr))
            if idx:
                col.set_alignment(1.0)
            col.set_resizable(True)
            self.detail_tree.append_column(col)
            self.detail_tree.proportions.append(proportion)
        
        self.detail_tree.connect("size-allocate", self._update_detail_column_widths)
        self.detail_tree.connect("key-press-event", self.on_detail_key_press)
        
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.add(self.detail_tree)
        frame.add(scrolled_window)
        
        button_box = Gtk.Box(spacing=10, margin_top=10)
        content_box.pack_start(button_box, False, False, 0)
        
        self.remove_button = Gtk.Button(label="Remove selected")
        self.remove_button.connect("clicked", self.on_remove_entry_clicked, selected_date)
        self.remove_button.set_sensitive(False)
        button_box.pack_start(self.remove_button, False, False, 0)
        
        self.selection = self.detail_tree.get_selection()
        self.selection.connect("changed", self.on_entry_selected)
        
        self.detail_dialog.show_all()

    def on_detail_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Delete:
            selection = widget.get_selection()
            if selection.count_selected_rows() > 0:
                self.on_remove_entry_clicked(None, None)
                return True
        return False

    def on_query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        if keyboard_mode:
            return False
            
        bin_x, bin_y = widget.convert_widget_to_bin_window_coords(x, y)
        result = widget.get_path_at_pos(bin_x, bin_y)
        if not result:
            return False
            
        path, column, cell_x, cell_y = result
        model = widget.get_model()
        iter = model.get_iter(path)
        date = model.get_value(iter, 0)
        
        has_bmr_settings = all(k in self.diet_settings for k in ['date_of_birth', 'height_cm', 'gender'])
        if not has_bmr_settings:
            tooltip.set_text("Complete diet settings (birth date, height, gender) and enter weight to show nutrition analysis.")
            widget.set_tooltip_cell(tooltip, path, column, None)
            return True
            
        weight = next((e.get('weight', 0) for e in self.journal_data if e['date'] == date), 0)
        if weight <= 0:
            tooltip.set_text("Enter your weight for this date to show nutrition analysis.")
            widget.set_tooltip_cell(tooltip, path, column, None)
            return True
            
        try:
            dob = self.diet_settings['date_of_birth']
            height = self.diet_settings['height_cm']
            gender = self.diet_settings['gender']
            birth_year = int(dob[:4])
            age = datetime.now().year - birth_year
            bmr = calculate_bmr(gender, weight, height, age)
        except Exception as e:
            print(f"BMR calculation error: {e}")
            tooltip.set_text("Error calculating nutrition analysis.")
            widget.set_tooltip_cell(tooltip, path, column, None)
            return True
            
        daily_values = {}
        for entry in self.journal_data:
            if entry['date'] == date:
                for nutrient in ['kcal', 'carbs', 'fat', 'protein', 'fiber', 'salt']:
                    daily_values[nutrient] = daily_values.get(nutrient, 0) + entry.get(nutrient, 0)
        
        daily_kcal = daily_values.get('kcal', 0)
        tooltip_lines = [
            f"BMR:\t\t{bmr:.0f} kcal",
            f"Calories:\t{daily_kcal:.0f} kcal"
        ]
        
        if self.diet_settings.get('diet'):
            remaining = calculate_remaining(daily_values, self.diet_settings.get('diet'), bmr)
            
            for nutrient, data in remaining.items():
                if nutrient == 'kcal':
                    current = data.get('current', 0)
                    max_val = data.get('max', 0)
                    if max_val <= 0:
                        continue
                    exceeded = current - max_val
                    status = f"Remaining: {-exceeded:.0f} kcal" if exceeded <= 0 else f"Exceeded by: {exceeded:.0f} kcal"
                    tooltip_lines.append(f"Calories (diet):\t{data.get('percent', 0):.0f}%\t\t{status}")
                elif nutrient in ['salt', 'fiber']:
                    current = data.get('grams', 0)
                    max_val = data.get('max', 1)
                    if max_val <= 0:
                        continue
                    exceeded = current - max_val
                    status = f"Remaining: {-exceeded:.1f}g" if exceeded <= 0 else f"Exceeded by: {exceeded:.1f}g"
                    tooltip_lines.append(f"{nutrient.capitalize()}:\t\t{current/max_val*100:.0f}%\t\t{status}")
                elif nutrient in ['fat', 'protein', 'carbs']:
                    current_grams = data.get('grams', 0)
                    max_percent = data.get('max_percent', 0)
                    kcal_per_gram = 9 if nutrient == 'fat' else 4
                    
                    if max_percent <= 0 or bmr <= 0:
                        continue
                    
                    max_grams = (max_percent / 100) * bmr / kcal_per_gram
                    if max_grams <= 0:
                        continue
                    
                    percent = (current_grams / max_grams * 100)
                    exceeded = current_grams - max_grams
                    status = f"Remaining: {-exceeded:.1f}g" if exceeded <= 0 else f"Exceeded by: {exceeded:.1f}g"
                    tooltip_lines.append(f"{nutrient.capitalize()}:\t{percent:.0f}%\t\t{status}")
        
        tooltip.set_text("\n".join(tooltip_lines))
        widget.set_tooltip_cell(tooltip, path, column, None)
        return True

    def _update_detail_column_widths(self, widget, allocation):
        if allocation.width > 1:
            total_width = allocation.width - 30
            sum_prop = sum(widget.proportions)
            for column, proportion in zip(widget.get_columns(), widget.proportions):
                column.set_fixed_width(int(total_width * proportion / sum_prop))

    def on_entry_selected(self, selection):
        model, paths = selection.get_selected_rows()
        self.remove_button.set_sensitive(len(paths) > 0)

    def on_remove_entry_clicked(self, widget, selected_date):
        selection = self.detail_tree.get_selection()
        model, paths = selection.get_selected_rows()
        
        if not paths:
            return

        confirm_dialog = Gtk.MessageDialog(
            transient_for=self.detail_dialog,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Remove {len(paths)} selected entries?"
        )
        
        response = confirm_dialog.run()
        confirm_dialog.destroy()
        
        if response == Gtk.ResponseType.YES:
            paths.sort(reverse=True)
            removed_indices = [p.get_indices()[0] for p in paths]
            
            # Remove entries from journal data
            for idx in removed_indices:
                if 0 <= idx < len(self.selected_date_entries):
                    entry = self.selected_date_entries[idx]
                    if entry in self.journal_data:
                        self.journal_data.remove(entry)
            
            self._save_journal()
            self._refresh_journal_view()
            
            # Update detail view
            self.selected_date_entries = [e for e in self.journal_data if e['date'] == selected_date]
            self.selected_date_entries.sort(key=lambda x: x['timestamp'], reverse=True)
            self.detail_store.clear()
            for entry in self.selected_date_entries:
                self.detail_store.append([
                    entry.get('ate', 'N/A'),
                    entry.get('gram', 0),
                    entry.get('kcal', 0),
                    entry.get('carbs', 0),
                    entry.get('sugar', 0),
                    entry.get('fat', 0),
                    entry.get('protein', 0),
                    entry.get('fiber', 0),
                    entry.get('salt', 0),
                    entry.get('cost', 0)
                ])
        
        selection.unselect_all()
        self.remove_button.set_sensitive(False)

    def _populate_journal_store(self):
        self.journal_store.clear()
        daily_data = {}
        
        for entry in self.journal_data:
            date = entry['date']
            if date not in daily_data:
                daily_data[date] = {k: 0.0 for k in [
                    'gram', 'kcal', 'carbs', 'sugar', 'fat', 
                    'protein', 'fiber', 'salt', 'cost'
                ]}
                daily_data[date]['weight'] = entry.get('weight', 0)
            
            for nutrient in daily_data[date]:
                if nutrient in entry:
                    daily_data[date][nutrient] += entry[nutrient]
            daily_data[date]['weight'] = entry.get('weight', daily_data[date]['weight'])

        for date, values in sorted(daily_data.items(), key=lambda x: x[0], reverse=True):
            self.journal_store.append([date] + [values[k] for k in [
                'gram', 'kcal', 'carbs', 'sugar', 'fat', 
                'protein', 'fiber', 'salt', 'cost'
            ]])

    def _refresh_journal_view(self):
        self._populate_journal_store()
        for tab in [self.weight_tab, self.bmr_tab, self.macro_tab]:
            if tab and hasattr(tab, 'update_plot'):
                tab.update_plot()
            if tab and hasattr(tab, 'update_bmr_plot'):
                tab.update_bmr_plot()
            if tab and hasattr(tab, 'update_charts'):
                tab.update_charts()
        self.journal_tree.queue_draw()

    def _save_journal(self):
        try:
            with open(os.path.join(self.db_dir, 'journal.json'), 'w', encoding='utf-8') as f:
                json.dump({'entries': self.journal_data}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self._show_error(f"Error saving journal: {e}")

    def on_add_to_journal_clicked(self, widget):
        weight_text = self.weight_entry.get_text().strip().replace(',', '.')
        if not weight_text:
            self._show_error("Enter your weight in 'My weight (kg)'")
            return
        try:
            weight = float(weight_text)
        except ValueError:
            self._show_error("Invalid value in 'My weight (kg)' - must be a number (e.g. 75.5 or 75,5)")
            return

        ingredient_name = self.ingredient_combo.get_active_text()
        recipe_name = self.recipe_combo.get_active_text()
        gram_text = self.gram_entry.get_text().strip().replace(',', '.')
        
        if not gram_text:
            self._show_error("Enter a weight in 'Grams'")
            return
        try:
            gram = float(gram_text)
            if gram < 0:
                raise ValueError
        except ValueError:
            self._show_error("Invalid value in 'Grams' - must be a positive number (e.g. 200 or 200.5)")
            return

        if ingredient_name and recipe_name:
            self._show_error("Select either an ingredient or a recipe, not both")
            return
        elif not ingredient_name and not recipe_name:
            self._show_error("Select an ingredient or a recipe")
            return

        if self.add_to_selected_check.get_active():
            selection = self.journal_tree.get_selection()
            model, treeiter = selection.get_selected()
            if not treeiter:
                self._show_error("Select a date in the journal to add the entry to.")
                return
            selected_date = model[treeiter][0]
            try:
                datetime.strptime(selected_date, "%Y-%m-%d")
            except ValueError:
                self._show_error("Invalid date selected.")
                return
            date = selected_date
            timestamp = f"{date} 23:59:59"
        else:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            date = datetime.now().strftime("%Y-%m-%d")

        entry = {'timestamp': timestamp, 'date': date, 'weight': weight, 'gram': gram}
        
        if ingredient_name:
            item = next((i for i in self.ingredients_data if i['name'] == ingredient_name), None)
            if not item:
                self._show_error("Selected ingredient not found")
                return
            factor = gram / 100
            entry.update({
                'ate': ingredient_name,
                'kcal': item['kcal'] * factor,
                'carbs': item['carbs'] * factor,
                'sugar': item['sugar'] * factor,
                'fat': item['fat'] * factor,
                'protein': item['protein'] * factor,
                'fiber': item['fiber'] * factor,
                'salt': item['salt'] * factor,
                'cost': item['cost'] * factor
            })
        elif recipe_name:
            recipe = next((r for r in self.recipes_data if r['name'] == recipe_name), None)
            if not recipe:
                self._show_error("Selected recipe not found")
                return
            total_gram = sum(ing['gram'] for ing in recipe['ingredients'])
            if total_gram == 0:
                self._show_error("Recipe has no ingredients")
                return
            factor = gram / total_gram
            entry.update({
                'ate': recipe_name,
                'kcal': sum(ing['kcal'] for ing in recipe['ingredients']) * factor,
                'carbs': sum(ing['carbs'] for ing in recipe['ingredients']) * factor,
                'sugar': sum(ing['sugar'] for ing in recipe['ingredients']) * factor,
                'fat': sum(ing['fat'] for ing in recipe['ingredients']) * factor,
                'protein': sum(ing['protein'] for ing in recipe['ingredients']) * factor,
                'fiber': sum(ing['fiber'] for ing in recipe['ingredients']) * factor,
                'salt': sum(ing['salt'] for ing in recipe['ingredients']) * factor,
                'cost': sum(ing['cost'] for ing in recipe['ingredients']) * factor
            })

        self.journal_data.append(entry)
        self._save_journal()
        self._refresh_journal_view()
        
        if self.weight_tab and hasattr(self.weight_tab, 'update_plot'):
            self.weight_tab.update_plot()
        if self.bmr_tab and hasattr(self.bmr_tab, 'update_bmr_plot'):
            self.bmr_tab.update_bmr_plot()
        if self.macro_tab and hasattr(self.macro_tab, 'update_charts'):
            self.macro_tab.update_charts()

    def detail_cell_data_func(self, column, cell, model, iter, data):
        col_index, total_kcal, bmr = data
        format_map = {
            1: "{:.1f}", 2: "{:.1f}", 3: "{:.1f}", 4: "{:.1f}",
            5: "{:.1f}", 6: "{:.1f}", 7: "{:.1f}", 8: "{:.1f}", 9: "{:.2f}"
        }
        value = model.get_value(iter, col_index)
        cell.set_property("text", format_map.get(col_index, "{:.1f}").format(float(value)) if col_index else str(value))
        
        cell.set_property("background-set", False)
        cell.set_property("foreground-set", False)

        if bmr is not None:
            colors = get_diet_colors(self.diet_settings.get('diet', ''), col_index, value, bmr, bmr)
            if colors:
                if 'background' in colors:
                    cell.set_property("background", colors['background'])
                    cell.set_property("background-set", True)
                if 'foreground' in colors:
                    cell.set_property("foreground", colors['foreground'])
                    cell.set_property("foreground-set", True)

    def cell_data_func(self, column, cell, model, iter, col_index):
        format_map = {
            1: "{:.1f}", 2: "{:.1f}", 3: "{:.1f}", 4: "{:.1f}",
            5: "{:.1f}", 6: "{:.1f}", 7: "{:.1f}", 8: "{:.1f}", 9: "{:.2f}"
        }
        value = model.get_value(iter, col_index)
        cell.set_property("text", format_map.get(col_index, "{:.1f}").format(float(value)) if col_index else str(value))
        
        cell.set_property("background-set", False)
        cell.set_property("foreground-set", False)

        date = model.get_value(iter, 0)
        weight = next((e.get('weight', 0) for e in self.journal_data if e['date'] == date), 0)
        
        if (weight > 0 and all(k in self.diet_settings for k in ['date_of_birth', 'height_cm', 'gender'])):
            try:
                dob = self.diet_settings['date_of_birth']
                height = self.diet_settings['height_cm']
                gender = self.diet_settings['gender']
                birth_year = int(dob[:4])
                age = datetime.now().year - birth_year
                bmr = calculate_bmr(gender, weight, height, age)
                
                colors = get_diet_colors(self.diet_settings.get('diet', ''), col_index, value, bmr, bmr)
                if colors:
                    if 'background' in colors:
                        cell.set_property("background", colors['background'])
                        cell.set_property("background-set", True)
                    if 'foreground' in colors:
                        cell.set_property("foreground", colors['foreground'])
                        cell.set_property("foreground-set", True)
            except Exception as e:
                print(f"Error calculating BMR: {e}")

    def _update_column_widths(self, widget, allocation):
        if allocation.width > 1:
            total_width = allocation.width - 30
            sum_prop = sum(widget.proportions)
            for column, proportion in zip(widget.get_columns(), widget.proportions):
                column.set_fixed_width(int(total_width * proportion / sum_prop))

    def _sort_func(self, model, iter1, iter2, sort_column_id):
        val1 = model.get_value(iter1, sort_column_id)
        val2 = model.get_value(iter2, sort_column_id)
        if sort_column_id == 0:
            return (val1 > val2) - (val1 < val2)
        try:
            return (float(val1) > float(val2)) - (float(val1) < float(val2))
        except (ValueError, TypeError):
            return 0

    def _show_error(self, message):
        dialog = Gtk.MessageDialog(
            transient_for=self.get_toplevel(),
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=message
        )
        dialog.run()
        dialog.destroy()
