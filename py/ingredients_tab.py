import gi
import json
import os
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

class IngredientsTab(Gtk.Box):
    def __init__(self, window_width, window_height, recipes_tab=None, journal_tab=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.set_border_width(10)
        self.recipes_tab = recipes_tab
        self.journal_tab = journal_tab
        self.db_dir = os.path.join(os.path.dirname(__file__), '../db')
        self.ingredients_data = self._load_ingredients()
        self.ingredients_store = Gtk.ListStore(str, float, float, float, float, float, float, float, float)
        self._populate_ingredients_store()

        self.ingredients_tree = Gtk.TreeView(model=self.ingredients_store)
        self._create_columns([
            ("Ingredient", 0.5), ("Kcal", 0.07), ("Carbs", 0.07), ("Sugar", 0.07),
            ("Fat", 0.07), ("Protein", 0.07), ("Fiber", 0.07), ("Salt", 0.07), ("Cost/hg", 0.04)
        ])

        # Enable multi-select with Shift/Ctrl-click
        self.ingredients_tree.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.add(self.ingredients_tree)

        frame = Gtk.Frame()
        frame.add(scrolled_window)
        self.pack_start(frame, True, True, 0)

        button_box = Gtk.Box(spacing=0)
        button_box.set_margin_top(0)
        self.pack_start(button_box, False, False, 0)

        self.remove_button = Gtk.Button(label="Remove ingredient")
        self.remove_button.set_margin_end(5)
        self.remove_button.connect("clicked", self.on_remove_clicked)
        button_box.pack_start(self.remove_button, False, False, 0)

        self.add_button = Gtk.Button(label="Add ingredient")
        self.add_button.set_margin_start(5)
        self.add_button.connect("clicked", self.on_add_clicked)
        button_box.pack_end(self.add_button, False, False, 0)

        self.update_button = Gtk.Button(label="Update")
        self.update_button.set_margin_end(5)
        self.update_button.set_sensitive(False)
        self.update_button.connect("clicked", self.on_update_clicked)
        button_box.pack_end(self.update_button, False, False, 0)

        # Connect signals
        self.ingredients_tree.get_selection().connect("changed", self.on_selection_changed)
        self.ingredients_tree.connect("row-activated", self.on_row_activated)
        
        # Connect keyboard events
        self.ingredients_tree.connect("key-press-event", self.on_key_press)

    def on_key_press(self, widget, event):
        # Handle Delete key
        if event.keyval == Gdk.KEY_Delete:
            self.on_remove_clicked(None)
            return True
        return False

    def _load_ingredients(self):
        try:
            with open(os.path.join(self.db_dir, 'ingredients.json'), 'r', encoding='utf-8') as f:
                return json.load(f).get('ingredients', [])
        except Exception as e:
            print(f"Error loading ingredients: {e}")
            return []

    def on_row_activated(self, treeview, path, column):
        self.on_update_clicked(None)

    def on_selection_changed(self, selection):
        model, paths = selection.get_selected_rows()
        self.update_button.set_sensitive(len(paths) > 0)

    def on_remove_clicked(self, widget):
        selection = self.ingredients_tree.get_selection()
        model, paths = selection.get_selected_rows()
        
        if not paths:
            return
            
        # Create list of all selected ingredient names
        ingredient_names = []
        for path in paths:
            treeiter = model.get_iter(path)
            ingredient_names.append(model.get_value(treeiter, 0))
        
        # Confirm deletion
        dialog = Gtk.MessageDialog(
            transient_for=self.get_toplevel(),
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Remove {len(ingredient_names)} selected ingredients?",
        )
        dialog.format_secondary_text("\n".join(ingredient_names))
        response = dialog.run()
        dialog.destroy()
        
        if response == Gtk.ResponseType.YES:
            # Remove from model in reverse order to avoid index issues
            for path in sorted(paths, reverse=True):
                treeiter = model.get_iter(path)
                model.remove(treeiter)
            
            # Update data list
            self.ingredients_data = [
                i for i in self.ingredients_data 
                if i['name'] not in ingredient_names
            ]
            
            self._save_ingredients()
            if self.recipes_tab:
                self.recipes_tab.reload_ingredients()
            if self.journal_tab:
                self.journal_tab.reload_ingredients()

    def on_update_clicked(self, widget):
        selection = self.ingredients_tree.get_selection()
        model, paths = selection.get_selected_rows()
        if paths and len(paths) == 1:  # Only update if one row is selected
            treeiter = model.get_iter(paths[0])
            self._show_ingredient_dialog(
                title="Update Ingredient",
                values=[model.get_value(treeiter, i) for i in range(9)],
                is_update=True
            )

    def on_add_clicked(self, widget):
        self._show_ingredient_dialog(
            title="Add New Ingredient",
            values=[""] + [0.0] * 8,
            is_update=False
        )

    def _show_ingredient_dialog(self, title, values, is_update):
        dialog = Gtk.Dialog(
            title=title,
            transient_for=self.get_toplevel(),
            modal=True,
            border_width=10
        )
        dialog.set_default_size(400, 150)

        content_area = dialog.get_content_area()
        content_area.set_spacing(5)
        
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        main_box.set_margin_top(5)
        main_box.set_margin_bottom(5)
        content_area.add(main_box)

        input_frame = Gtk.Frame(label=" Ingredient details ")
        input_frame.set_label_align(0.5, 0.5)
        input_frame.set_margin_top(5)
        input_frame.set_margin_bottom(5)
        main_box.pack_start(input_frame, True, True, 0)

        input_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        input_box.set_margin_top(10)
        input_box.set_margin_bottom(10)
        input_box.set_margin_start(10)
        input_box.set_margin_end(10)
        input_frame.add(input_box)

        input_grid = Gtk.Grid()
        input_grid.set_column_spacing(5)
        input_grid.set_row_spacing(5)
        input_box.pack_start(input_grid, True, True, 0)

        self.entry_name = Gtk.Entry(placeholder_text="Ingredient name")
        self.entry_name.set_text(values[0])
        self.entry_name.set_hexpand(True)
        input_grid.attach(self.entry_name, 0, 0, 1, 1)

        fields = [
            ("Kcal", "kcal", 1), ("Carbs", "carbs", 2), ("Sugar", "sugar", 3),
            ("Fat", "fat", 4), ("Protein", "protein", 5), ("Fiber", "fiber", 6),
            ("Salt", "salt", 7), ("Cost", "cost", 8)
        ]

        for i, (placeholder, prop_name, idx) in enumerate(fields, start=1):
            entry = Gtk.Entry(placeholder_text=placeholder)
            entry.set_input_purpose(Gtk.InputPurpose.NUMBER)
            entry.set_width_chars(6)
            entry.set_max_width_chars(8)
            entry.set_text(str(values[idx]) if values[idx] != 0.0 else "")
            setattr(self, f"entry_{prop_name}", entry)
            input_grid.attach(entry, i, 0, 1, 1)

        self.update_recipes_check = Gtk.CheckButton(label="Also update recipes")
        main_box.pack_start(self.update_recipes_check, False, False, 0)

        self.update_journal_check = Gtk.CheckButton(label="Also update journal")
        main_box.pack_start(self.update_journal_check, False, False, 0)

        button_box = Gtk.Box(spacing=10)
        button_box.set_halign(Gtk.Align.FILL)
        button_box.set_margin_top(10)
        main_box.pack_end(button_box, False, False, 0)
        
        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", lambda w: dialog.destroy())
        button_box.pack_start(cancel_button, False, False, 0)
        
        action_button = Gtk.Button(label="Update" if is_update else "Add")
        action_button.connect("clicked", lambda w: self._save_ingredient(dialog, is_update))
        button_box.pack_end(action_button, False, False, 0)
        
        dialog.show_all()

    def _parse_float(self, text):
        text = text.strip()
        if not text:
            return 0.0
        try:
            return float(text.replace(',', '.'))
        except ValueError:
            raise ValueError(f"Invalid number: {text}")

    def _save_ingredient(self, dialog, is_update):
        try:
            new_name = self.entry_name.get_text().strip()
            if not new_name:
                raise ValueError("Ingredient name is required")

            new_values = {
                'name': new_name,
                'kcal': self._parse_float(self.entry_kcal.get_text()),
                'carbs': self._parse_float(self.entry_carbs.get_text()),
                'sugar': self._parse_float(self.entry_sugar.get_text()),
                'fat': self._parse_float(self.entry_fat.get_text()),
                'protein': self._parse_float(self.entry_protein.get_text()),
                'fiber': self._parse_float(self.entry_fiber.get_text()),
                'salt': self._parse_float(self.entry_salt.get_text()),
                'cost': self._parse_float(self.entry_cost.get_text())
            }

            if is_update:
                selection = self.ingredients_tree.get_selection()
                model, paths = selection.get_selected_rows()
                if paths and len(paths) == 1:
                    treeiter = model.get_iter(paths[0])
                    old_name = model.get_value(treeiter, 0)
                    
                    # Update the ListStore
                    for i, value in enumerate(new_values.values()):
                        model.set_value(treeiter, i, value)
                    
                    # Update local data
                    for i, ingredient in enumerate(self.ingredients_data):
                        if ingredient['name'].lower() == old_name.lower():
                            self.ingredients_data[i] = new_values
                            break
                    
                    # Update recipes if checked
                    if self.update_recipes_check.get_active():
                        updated = self._update_recipes(old_name, new_values)
                        if updated and self.recipes_tab:
                            self.recipes_tab.reload_recipes()
                    
                    # Update journal if checked
                    if self.update_journal_check.get_active():
                        updated = self._update_journal(old_name, new_values)
                        if updated and self.journal_tab:
                            self.journal_tab.reload_journal()
                            self.journal_tab._refresh_journal_view()
            else:
                # Check for existing ingredient
                existing = next((i for i in self.ingredients_data if i['name'].lower() == new_name.lower()), None)
                if existing:
                    if not self._confirm_overwrite(new_name):
                        return
                    self.ingredients_data.remove(existing)
                    # Remove from ListStore
                    for row in self.ingredients_store:
                        if row[0].lower() == new_name.lower():
                            self.ingredients_store.remove(row.iter)
                            break

                self.ingredients_data.append(new_values)
                self.ingredients_store.append(list(new_values.values()))

            self._save_ingredients()
            if self.recipes_tab:
                self.recipes_tab.reload_ingredients()
            if self.journal_tab:
                self.journal_tab.reload_ingredients()
            self.ingredients_store.set_sort_column_id(0, Gtk.SortType.ASCENDING)
            dialog.destroy()

        except Exception as e:
            self._show_error_dialog(dialog, "Error saving ingredient", str(e))

    def _update_recipes(self, old_name, new_values):
        try:
            filepath = os.path.join(self.db_dir, 'recipes.json')
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            updated = False
            for recipe in data['recipes']:
                for ingredient in recipe['ingredients']:
                    if ingredient['name'].lower() == old_name.lower():
                        # Update the name
                        ingredient['name'] = new_values['name']
                        # Recalculate all nutritional values based on grams
                        grams = ingredient['gram']
                        for key in ['kcal', 'carbs', 'sugar', 'fat', 'protein', 'fiber', 'salt', 'cost']:
                            ingredient[key] = new_values[key] * (grams / 100)
                        updated = True
            
            if updated:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            return updated
        except Exception as e:
            print(f"Error updating recipes: {e}")
            return False

    def _update_journal(self, old_name, new_values):
        try:
            filepath = os.path.join(self.db_dir, 'journal.json')
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            updated = False
            for entry in data['entries']:
                if entry['ate'].lower() == old_name.lower():
                    # Update the name
                    entry['ate'] = new_values['name']
                    # Recalculate all nutritional values based on grams
                    grams = entry['gram']
                    for key in ['kcal', 'carbs', 'sugar', 'fat', 'protein', 'fiber', 'salt', 'cost']:
                        entry[key] = new_values[key] * (grams / 100)
                    updated = True
            
            if updated:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            return updated
        except Exception as e:
            print(f"Error updating journal: {e}")
            return False

    def _confirm_overwrite(self, name):
        dialog = Gtk.MessageDialog(
            transient_for=self.get_toplevel(),
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Ingredient '{name}' already exists",
        )
        dialog.format_secondary_text("Do you want to overwrite it with these new values?")
        response = dialog.run() == Gtk.ResponseType.YES
        dialog.destroy()
        return response

    def _show_error_dialog(self, parent, text, secondary_text):
        dialog = Gtk.MessageDialog(
            transient_for=parent,
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=text,
        )
        dialog.format_secondary_text(secondary_text)
        dialog.run()
        dialog.destroy()

    def _save_ingredients(self):
        try:
            with open(os.path.join(self.db_dir, 'ingredients.json'), 'w', encoding='utf-8') as f:
                json.dump({'ingredients': self.ingredients_data}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self._show_error_dialog(self.get_toplevel(), "Error saving ingredients", str(e))

    def _populate_ingredients_store(self):
        for ingredient in sorted(self.ingredients_data, key=lambda x: x['name'].lower()):
            self.ingredients_store.append([
                ingredient['name'],
                ingredient['kcal'],
                ingredient['carbs'],
                ingredient['sugar'],
                ingredient['fat'],
                ingredient['protein'],
                ingredient['fiber'],
                ingredient['salt'],
                ingredient['cost']
            ])

    def _create_columns(self, columns):
        for idx, (col_name, proportion) in enumerate(columns):
            renderer = Gtk.CellRendererText()
            if idx != 0:
                renderer.set_property("xalign", 1.0)
            col = Gtk.TreeViewColumn(col_name, renderer)
            col.set_cell_data_func(renderer, self._cell_data_func, idx)
            if idx != 0:
                col.set_alignment(1.0)
            col.set_resizable(True)
            col.set_sort_column_id(idx)
            col.set_clickable(True)
            self.ingredients_tree.append_column(col)
        
        self.ingredients_store.set_sort_column_id(0, Gtk.SortType.ASCENDING)
        self.ingredients_tree.connect("size-allocate", self._update_column_widths, [p for _, p in columns])

    def _cell_data_func(self, column, cell, model, iter, col_index):
        value = model.get_value(iter, col_index)
        if col_index == 0:
            cell.set_property("text", str(value))
        else:
            try:
                if col_index in (1, 2, 3, 4, 5):
                    formatted = f"{float(value):.1f}"
                elif col_index in (6, 7):
                    formatted = f"{float(value):.2f}"
                elif col_index == 8:
                    formatted = f"{float(value):.3f}"
                else:
                    formatted = str(value)
            except (ValueError, TypeError):
                formatted = str(value)
            cell.set_property("text", formatted)

    def _update_column_widths(self, widget, allocation, proportions):
        if allocation.width > 1:
            total_width = allocation.width - 30
            sum_prop = sum(proportions)
            for column, proportion in zip(widget.get_columns(), proportions):
                column.set_fixed_width(int(total_width * (proportion / sum_prop)))
