import gi
import json
import os
import sys
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GdkPixbuf

class RecipesTab(Gtk.Box):
    def __init__(self, window_width, window_height, parent=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.set_border_width(10)
        self.parent = parent
        self.db_dir = self._get_db_dir()
        self.ingredients_data = []
        self.recipes_data = []
        
        # Initialize all widgets first
        self._init_widgets(window_width)
        
        # Then load data
        self.reload_ingredients()
        self._load_recipes()
        
        self.connect("map", self._on_map)

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

    def _init_widgets(self, window_width):
        # Recipe list setup
        self.recipe_store = Gtk.ListStore(str, float, float, float, float, float, float, float, float, float)
        self.recipe_tree = Gtk.TreeView(model=self.recipe_store)
        self._create_columns(self.recipe_tree, [
            ("Recipe Name", 0.4), ("Gram", 0.07), ("Kcal", 0.07), ("Carbs", 0.07), ("Sugar", 0.07),
            ("Fat", 0.07), ("Protein", 0.07), ("Fiber", 0.07), ("Salt", 0.07), ("Cost", 0.04)
        ], sortable=True)
        self.recipe_tree.get_selection().connect("changed", self.on_recipe_selected)
        self.recipe_store.set_sort_column_id(0, Gtk.SortType.ASCENDING)

        # Top section with recipe list
        recipe_scrolled = Gtk.ScrolledWindow()
        recipe_scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        recipe_scrolled.add(self.recipe_tree)
        recipe_frame = Gtk.Frame()
        recipe_frame.add(recipe_scrolled)
        self.pack_start(recipe_frame, True, True, 0)

        # Button box
        button_box = Gtk.Box(spacing=10)
        self.pack_start(button_box, False, False, 0)
        
        # Initialize buttons
        self.delete_btn = Gtk.Button(label="Delete Recipe")
        self.new_btn = Gtk.Button(label="New Recipe")
        self.copy_btn = Gtk.Button(label="Copy Recipe")
        self.save_btn = Gtk.Button(label="Save Recipe")
        
        # Connect signals after all widgets are initialized
        self.delete_btn.connect("clicked", self._on_delete_recipe_clicked)
        self.new_btn.connect("clicked", self._on_new_recipe_clicked)
        self.copy_btn.connect("clicked", self._on_copy_recipe_clicked)
        self.save_btn.connect("clicked", self._on_save_recipe_clicked)
        
        for btn in [self.delete_btn, self.new_btn, self.copy_btn, self.save_btn]:
            button_box.pack_start(btn, True, True, 0)

        # Lower container with split pane
        self.lower_container = Gtk.HPaned()
        self.lower_container.set_position(int(window_width * 0.618))
        self.lower_container.connect("size-allocate", self._update_paned_position)
        self.pack_start(self.lower_container, True, True, 0)

        # Left container setup
        self.left_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        
        # Ingredients table
        self.ingredient_store = Gtk.ListStore(str, float, float, float, float, float, float, float, float, float)
        self.ingredient_tree = Gtk.TreeView(model=self.ingredient_store)
        self._create_columns(self.ingredient_tree, [
            ("Ingredient", 0.19), ("Gram", 0.10), ("Kcal", 0.09), ("Carbs", 0.10), ("Sugar", 0.10),
            ("Fat", 0.08), ("Protein", 0.12), ("Fiber", 0.1), ("Salt", 0.08), ("Cost", 0.04)
        ], sortable=True)
        self.ingredient_store.set_sort_column_id(0, Gtk.SortType.ASCENDING)

        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.scrolled_window.add(self.ingredient_tree)
        
        table_frame = Gtk.Frame()
        table_frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        table_frame.set_margin_start(5)
        table_frame.set_margin_end(5)
        table_frame.set_margin_top(5)
        table_frame.set_margin_bottom(0)
        table_frame.add(self.scrolled_window)
        self.left_container.pack_start(table_frame, True, True, 0)

        # Header row
        self.header_store = Gtk.ListStore(str)
        self.header_tree = Gtk.TreeView(model=self.header_store)
        self._create_header_columns(self.header_tree, [
            ("Per pts.", 0.18), ("", 0.10), ("", 0.09), ("", 0.10), ("", 0.10),
            ("", 0.08), ("", 0.12), ("", 0.1), ("", 0.08), ("", 0.04)
        ])
        self.header_tree.set_headers_visible(True)
        self.header_tree.set_property("height-request", 1)
        
        header_frame = Gtk.Frame()
        header_frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        header_frame.set_margin_start(5)
        header_frame.set_margin_end(5)
        header_frame.set_margin_bottom(0)
        header_frame.add(self.header_tree)
        self.left_container.pack_start(header_frame, False, False, 0)

        # Controls
        control_box = Gtk.Box(spacing=10)
        control_box.set_margin_start(5)
        control_box.set_margin_end(5)
        control_box.set_margin_bottom(5)
        
        self.delete_ingredient_btn = Gtk.Button(label="Delete Ingredient")
        self.delete_ingredient_btn.connect("clicked", self._on_delete_ingredient_clicked)
        control_box.pack_start(self.delete_ingredient_btn, False, False, 0)
        
        self.ingredient_combo = Gtk.ComboBoxText()
        self.gram_entry = Gtk.Entry()
        self.gram_entry.set_placeholder_text("Gram")
        self.gram_entry.set_width_chars(5)
        self.add_ingredient_btn = Gtk.Button(label="Add Ingredient")
        self.add_ingredient_btn.connect("clicked", self._on_add_ingredient_clicked)
        
        control_box.pack_end(self.add_ingredient_btn, False, False, 0)
        control_box.pack_end(self.gram_entry, False, False, 0)
        control_box.pack_end(self.ingredient_combo, False, False, 0)
        
        self.left_container.pack_start(control_box, False, False, 0)
        self.lower_container.add1(self.left_container)

        # Right container setup
        self.right_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        text_fields_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        text_fields_box.set_margin_start(5)
        text_fields_box.set_margin_end(5)
        text_fields_box.set_margin_top(5)
        text_fields_box.set_margin_bottom(0)

        self.recipe_name_entry = Gtk.Entry()
        self.recipe_name_entry.set_placeholder_text("Recipe name")
        self.recipe_name_entry.set_hexpand(True)
        text_fields_box.pack_start(self.recipe_name_entry, True, True, 0)

        self.portions_entry = Gtk.Entry()
        self.portions_entry.set_placeholder_text("Pts.")
        self.portions_entry.set_hexpand(False)
        self.portions_entry.set_width_chars(4)
        self.portions_entry.connect("changed", self._on_portions_changed)
        text_fields_box.pack_start(self.portions_entry, False, False, 0)

        self.right_container.pack_start(text_fields_box, False, False, 0)

        self.instructions = Gtk.TextView()
        self.instructions.set_wrap_mode(Gtk.WrapMode.WORD)
        self.instructions.set_left_margin(10)
        self.instructions.set_right_margin(10)
        self.instructions.set_top_margin(5)
        self.instructions.set_bottom_margin(5)

        instructions_scrolled = Gtk.ScrolledWindow()
        instructions_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        instructions_scrolled.add(self.instructions)
        instructions_scrolled.set_min_content_height(100)
        instructions_scrolled.set_propagate_natural_height(False)

        instructions_frame = Gtk.Frame()
        instructions_frame.set_label(" Instructions ")
        instructions_frame.set_label_align(0.5, 0.5)
        instructions_frame.set_margin_start(5)
        instructions_frame.set_margin_end(5)
        instructions_frame.set_margin_top(0)
        instructions_frame.set_margin_bottom(5)
        instructions_frame.add(instructions_scrolled)
        self.right_container.pack_start(instructions_frame, True, True, 0)

        self.lower_container.add2(self.right_container)

    def _populate_ingredient_combo(self):
        """Fill ingredient_combo with available ingredients"""
        self.ingredient_combo.remove_all()
        sorted_ingredients = sorted(self.ingredients_data, key=lambda x: x['name'].lower())
        for ingredient in sorted_ingredients:
            self.ingredient_combo.append_text(ingredient['name'])

    def reload_recipes(self):
        """Reload recipes from file and refresh the UI"""
        try:
            recipes_path = os.path.join(self.db_dir, 'recipes.json')
            with open(recipes_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.recipes_data = data['recipes']
                
                self.recipe_store.clear()
                for recipe in sorted(data['recipes'], key=lambda x: x['name'].lower()):
                    ingredients = recipe['ingredients']
                    self.recipe_store.append([
                        recipe['name'],
                        sum(ing['gram'] for ing in ingredients),
                        sum(ing['kcal'] for ing in ingredients),
                        sum(ing['carbs'] for ing in ingredients),
                        sum(ing['sugar'] for ing in ingredients),
                        sum(ing['fat'] for ing in ingredients),
                        sum(ing['protein'] for ing in ingredients),
                        sum(ing['fiber'] for ing in ingredients),
                        sum(ing['salt'] for ing in ingredients),
                        sum(ing['cost'] for ing in ingredients)
                    ])
                self.recipe_store.set_sort_column_id(0, Gtk.SortType.ASCENDING)
                
                self.reload_ingredients()
                
                selection = self.recipe_tree.get_selection()
                model, treeiter = selection.get_selected()
                if treeiter is not None:
                    self.on_recipe_selected(selection)
                    
        except Exception as e:
            print(f"Error reloading recipes from {recipes_path}: {e}")

    def reload_ingredients(self):
        """Reload ingredients from file and refresh the ingredient_combo"""
        try:
            ingredients_path = os.path.join(self.db_dir, 'ingredients.json')
            with open(ingredients_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.ingredients_data = data['ingredients']
                self._populate_ingredient_combo()
        except Exception as e:
            print(f"Error reloading ingredients from {ingredients_path}: {e}")

    def _load_recipes(self):
        """Load recipes from file during initialization"""
        try:
            recipes_path = os.path.join(self.db_dir, 'recipes.json')
            with open(recipes_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.recipes_data = data['recipes']
                for recipe in sorted(data['recipes'], key=lambda x: x['name'].lower()):
                    ingredients = recipe['ingredients']
                    self.recipe_store.append([
                        recipe['name'],
                        sum(ing['gram'] for ing in ingredients),
                        sum(ing['kcal'] for ing in ingredients),
                        sum(ing['carbs'] for ing in ingredients),
                        sum(ing['sugar'] for ing in ingredients),
                        sum(ing['fat'] for ing in ingredients),
                        sum(ing['protein'] for ing in ingredients),
                        sum(ing['fiber'] for ing in ingredients),
                        sum(ing['salt'] for ing in ingredients),
                        sum(ing['cost'] for ing in ingredients)
                    ])
        except Exception as e:
            print(f"Error loading recipes from {recipes_path}: {e}")

    def _on_add_ingredient_clicked(self, widget):
        ingredient_name = self.ingredient_combo.get_active_text()
        if not ingredient_name:
            self._show_error("No ingredient selected")
            return

        gram_text = self.gram_entry.get_text().strip()
        if not gram_text:
            self._show_error("No weight specified for ingredient")
            return

        try:
            gram = float(gram_text)
        except ValueError:
            self._show_error("Invalid weight value")
            return

        ingredient = next((i for i in self.ingredients_data if i['name'] == ingredient_name), None)
        if not ingredient:
            return

        factor = gram / 100
        self.ingredient_store.append([
            ingredient['name'],
            gram,
            ingredient['kcal'] * factor,
            ingredient['carbs'] * factor,
            ingredient['sugar'] * factor,
            ingredient['fat'] * factor,
            ingredient['protein'] * factor,
            ingredient['fiber'] * factor,
            ingredient['salt'] * factor,
            ingredient['cost'] * factor
        ])
        self.ingredient_store.set_sort_column_id(0, Gtk.SortType.ASCENDING)
        self._update_per_portion_values()

    def _on_delete_ingredient_clicked(self, widget):
        selection = self.ingredient_tree.get_selection()
        model, treeiter = selection.get_selected()
        if treeiter is None:
            return
        model.remove(treeiter)
        self._update_per_portion_values()

    def _update_per_portion_values(self):
        try:
            portions = int(self.portions_entry.get_text().strip()) if self.portions_entry.get_text().strip() else 1
        except ValueError:
            portions = 1

        totals = [0]*9
        for row in self.ingredient_store:
            for i in range(9):
                totals[i] += row[i+1]
        
        self._update_header_columns([t/portions for t in totals])

    def _on_copy_recipe_clicked(self, widget):
        recipe_name = self.recipe_name_entry.get_text().strip()
        if not recipe_name:
            return

        buffer = self.instructions.get_buffer()
        start_iter = buffer.get_start_iter()
        end_iter = buffer.get_end_iter()
        instructions = buffer.get_text(start_iter, end_iter, False)

        ingredients_text = ""
        for row in self.ingredient_store:
            ingredients_text += f"{row[1]}g {row[0]}\n"

        clipboard_text = f"{recipe_name}\n\n{ingredients_text}\n{instructions}"

        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(clipboard_text, -1)
        clipboard.store()

    def _on_portions_changed(self, entry):
        text = entry.get_text()
        if not text:
            return
            
        if not text.isdigit():
            pos = entry.get_position()
            filtered = ''.join([c for c in text if c.isdigit()])
            entry.set_text(filtered)
            entry.set_position(min(pos, len(filtered)))

    def _on_delete_recipe_clicked(self, widget):
        selection = self.recipe_tree.get_selection()
        model, treeiter = selection.get_selected()
        
        if treeiter is None:
            return
            
        recipe_name = model[treeiter][0]
        
        dialog = Gtk.MessageDialog(
            transient_for=self.get_toplevel(),
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=f"Delete recipe '{recipe_name}'?"
        )
        dialog.format_secondary_text("This action cannot be undone.")
        response = dialog.run()
        dialog.destroy()
        
        if response == Gtk.ResponseType.OK:
            self.recipes_data = [r for r in self.recipes_data if r['name'] != recipe_name]
            self.recipe_store.remove(treeiter)
            self._save_recipes_to_file()
            self._on_new_recipe_clicked(widget)

    def _on_save_recipe_clicked(self, widget):
        recipe_name = self.recipe_name_entry.get_text().strip()
        if not recipe_name:
            self._show_error("Recipe name cannot be empty")
            return
            
        portions_text = self.portions_entry.get_text().strip()
        try:
            portions = int(portions_text) if portions_text else 1
        except ValueError:
            portions = 1
            
        ingredients = []
        for row in self.ingredient_store:
            ingredients.append({
                'name': row[0],
                'gram': row[1],
                'kcal': row[2],
                'carbs': row[3],
                'sugar': row[4],
                'fat': row[5],
                'protein': row[6],
                'fiber': row[7],
                'salt': row[8],
                'cost': row[9]
            })
            
        buffer = self.instructions.get_buffer()
        start_iter = buffer.get_start_iter()
        end_iter = buffer.get_end_iter()
        instructions = buffer.get_text(start_iter, end_iter, False)
        
        existing_recipe = next((r for r in self.recipes_data if r['name'] == recipe_name), None)
        
        if existing_recipe:
            dialog = Gtk.MessageDialog(
                transient_for=self.get_toplevel(),
                flags=0,
                message_type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.OK_CANCEL,
                text=f"Recipe '{recipe_name}' already exists"
            )
            dialog.format_secondary_text("Do you want to overwrite it?")
            response = dialog.run()
            dialog.destroy()
            
            if response != Gtk.ResponseType.OK:
                return
                
            existing_recipe.update({
                'portions': portions,
                'ingredients': ingredients,
                'instructions': instructions
            })
        else:
            self.recipes_data.append({
                'name': recipe_name,
                'portions': portions,
                'ingredients': ingredients,
                'instructions': instructions
            })
            
            self.recipe_store.append([
                recipe_name,
                sum(ing['gram'] for ing in ingredients),
                sum(ing['kcal'] for ing in ingredients),
                sum(ing['carbs'] for ing in ingredients),
                sum(ing['sugar'] for ing in ingredients),
                sum(ing['fat'] for ing in ingredients),
                sum(ing['protein'] for ing in ingredients),
                sum(ing['fiber'] for ing in ingredients),
                sum(ing['salt'] for ing in ingredients),
                sum(ing['cost'] for ing in ingredients)
            ])
            self.recipe_store.set_sort_column_id(0, Gtk.SortType.ASCENDING)
        
        self._save_recipes_to_file()

    def _save_recipes_to_file(self):
        try:
            recipes_path = os.path.join(self.db_dir, 'recipes.json')
            with open(recipes_path, 'w', encoding='utf-8') as f:
                json.dump({'recipes': self.recipes_data}, f, indent=2, ensure_ascii=False)
            if self.parent and hasattr(self.parent, 'on_recipes_changed'):
                self.parent.on_recipes_changed()
        except Exception as e:
            self._show_error("Error saving recipes", str(e))

    def _on_new_recipe_clicked(self, widget):
        selection = self.recipe_tree.get_selection()
        selection.unselect_all()
        
        self.ingredient_store.clear()
        
        self.recipe_name_entry.set_text("")
        self.portions_entry.set_text("")
        self.portions_entry.set_placeholder_text("Pts.")
        
        buffer = self.instructions.get_buffer()
        buffer.set_text("")
        
        columns = self.header_tree.get_columns()
        for i in range(1, len(columns)):
            columns[i].set_title("")

    def _create_header_columns(self, treeview, columns):
        treeview.proportions = []
        for idx, (col_name, proportion) in enumerate(columns):
            col = Gtk.TreeViewColumn(col_name)
            if idx > 0:
                col.set_alignment(1.0)
            col.set_resizable(True)
            col.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
            treeview.append_column(col)
            treeview.proportions.append(proportion)
        treeview.connect("size-allocate", self._update_column_widths)

    def _update_header_columns(self, per_portion_values):
        columns = self.header_tree.get_columns()
        if len(columns) != len(per_portion_values) + 1:
            return
        format_mapping = {
            1: "{:.1f}",
            2: "{:.1f}",
            3: "{:.1f}",
            4: "{:.1f}",
            5: "{:.1f}",
            6: "{:.2f}",
            7: "{:.2f}",
            8: "{:.2f}",
            9: "{:.3f}"
        }
        
        for i, value in enumerate(per_portion_values):
            col_index = i + 1
            if col_index < len(columns):
                try:
                    formatted = format_mapping.get(col_index, "{}").format(float(value))
                    columns[col_index].set_title(formatted)
                except Exception:
                    columns[col_index].set_title(str(value))

    def on_recipe_selected(self, selection):
        model, treeiter = selection.get_selected()
        if treeiter is not None:
            recipe_name = model[treeiter][0]
            for recipe in self.recipes_data:
                if recipe['name'] == recipe_name:
                    self.recipe_name_entry.set_text(recipe['name'])
                    portions = recipe.get('portions', 1)
                    self.portions_entry.set_text(str(portions) if portions != 1 else "")
                    self.portions_entry.set_placeholder_text("Pts.")
                    
                    buffer = self.instructions.get_buffer()
                    buffer.set_text(recipe.get('instructions', ''))
                    
                    self.ingredient_store.clear()
                    totals = [0]*9
                    for ingredient in recipe['ingredients']:
                        self.ingredient_store.append([
                            ingredient['name'],
                            ingredient['gram'],
                            ingredient['kcal'],
                            ingredient['carbs'],
                            ingredient['sugar'],
                            ingredient['fat'],
                            ingredient['protein'],
                            ingredient['fiber'],
                            ingredient['salt'],
                            ingredient['cost']
                        ])
                        totals[0] += ingredient['gram']
                        totals[1] += ingredient['kcal']
                        totals[2] += ingredient['carbs']
                        totals[3] += ingredient['sugar']
                        totals[4] += ingredient['fat']
                        totals[5] += ingredient['protein']
                        totals[6] += ingredient['fiber']
                        totals[7] += ingredient['salt']
                        totals[8] += ingredient['cost']
                    
                    per_portion_values = [t/portions for t in totals]
                    self._update_header_columns(per_portion_values)
                    break

    def _create_columns(self, treeview, columns, sortable=False):
        treeview.proportions = []
        for idx, (col_name, proportion) in enumerate(columns):
            renderer = Gtk.CellRendererText()
            if idx != 0:
                renderer.set_property("xalign", 1.0)
            col = Gtk.TreeViewColumn(col_name, renderer)
            col.set_cell_data_func(renderer, self.cell_data_func, idx)
            if idx != 0:
                col.set_alignment(1.0)
            col.set_resizable(True)
            
            if sortable:
                col.set_sort_column_id(idx)
                col.set_clickable(True)
                treeview.get_model().set_sort_func(idx, self._sort_func, idx)
                
            treeview.append_column(col)
            treeview.proportions.append(proportion)
        treeview.connect("size-allocate", self._update_column_widths)

    def _sort_func(self, model, iter1, iter2, sort_column_id):
        val1 = model.get_value(iter1, sort_column_id)
        val2 = model.get_value(iter2, sort_column_id)
        
        if sort_column_id == 0:
            return (val1.lower() > val2.lower()) - (val1.lower() < val2.lower())
        
        try:
            return (float(val1) > float(val2)) - (float(val1) < float(val2))
        except (ValueError, TypeError):
            return 0

    def cell_data_func(self, column, cell, model, iter, col_index):
        format_mapping = {
            1: "{:.1f}",
            2: "{:.1f}",
            3: "{:.1f}",
            4: "{:.1f}",
            5: "{:.1f}",
            6: "{:.2f}",
            7: "{:.2f}",
            8: "{:.2f}",
            9: "{:.3f}"
        }
        value = model.get_value(iter, col_index)
        if col_index == 0:
            cell.set_property("text", str(value))
        else:
            try:
                formatted = format_mapping.get(col_index, "{}").format(float(value))
            except Exception:
                formatted = str(value)
            cell.set_property("text", formatted)

    def _update_column_widths(self, widget, allocation):
        if allocation.width <= 1:
            return
        total_width = allocation.width - 30
        sum_prop = sum(widget.proportions)
        for column, proportion in zip(widget.get_columns(), widget.proportions):
            column.set_fixed_width(int(total_width * (proportion / sum_prop)))

    def _update_paned_position(self, widget, allocation):
        desired_position = int(allocation.width * 0.618)
        if widget.get_position() != desired_position:
            widget.set_position(desired_position)

    def _on_map(self, widget):
        allocation = self.lower_container.get_allocation()
        self.lower_container.set_position(int(allocation.width * 0.618))

    def _show_error(self, text, secondary_text=None):
        dialog = Gtk.MessageDialog(
            transient_for=self.get_toplevel(),
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=text,
            secondary_text=secondary_text
        )
        dialog.run()
        dialog.destroy()
