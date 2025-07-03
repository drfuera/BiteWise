import gi
import json
import os
import sys
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GdkPixbuf

class AddIngredientDialog(Gtk.Dialog):
    def __init__(self, parent, ingredients_data):
        super().__init__(title="Add Ingredient", transient_for=parent, modal=True)
        self.set_default_size(400, 400)
        self.ingredients_data = ingredients_data
        self.filtered_ingredients = ingredients_data.copy()
        
        self.filter_entry = Gtk.Entry(placeholder_text="Filter ingredients...")
        self.filter_entry.connect("changed", self.on_filter_changed)

        self.ingredients_list = Gtk.ListStore(str)
        self.ingredients_view = Gtk.TreeView(model=self.ingredients_list)
        self.ingredients_view.set_headers_visible(False)
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Ingredients", renderer, text=0)
        self.ingredients_view.append_column(column)
        
        self.gram_entry = Gtk.Entry(placeholder_text="Grams", width_chars=7)
        self.gram_entry.connect("activate", self.on_add_clicked)

        content_area = self.get_content_area()
        content_area.set_spacing(10)
        content_area.set_margin_top(10)
        content_area.set_margin_bottom(10)
        content_area.set_margin_start(10)
        content_area.set_margin_end(10)

        main_frame = Gtk.Frame(label="Add Ingredient")
        content_area.pack_start(main_frame, True, True, 0)

        frame_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=10)
        main_frame.add(frame_box)

        frame_box.pack_start(self.filter_entry, False, False, 0)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.add(self.ingredients_view)
        frame_box.pack_start(scrolled_window, True, True, 0)

        grams_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        frame_box.pack_start(grams_box, False, False, 0)
        grams_box.pack_start(self.gram_entry, False, False, 0)
        
        button_box = Gtk.Box(spacing=10)
        frame_box.pack_start(button_box, False, False, 0)

        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", lambda b: self.destroy())
        button_box.pack_start(cancel_button, False, False, 0)

        button_box.pack_start(Gtk.Box(), True, True, 0)

        add_button = Gtk.Button(label="Add")
        add_button.connect("clicked", self.on_add_clicked)
        button_box.pack_start(add_button, False, False, 0)

        self.update_lists()
        self.show_all()

    def update_lists(self):
        self.ingredients_list.clear()
        for item in self.filtered_ingredients:
            self.ingredients_list.append([item['name']])

    def on_filter_changed(self, entry):
        filter_text = entry.get_text().lower()
        if not filter_text:
            self.filtered_ingredients = self.ingredients_data.copy()
        else:
            self.filtered_ingredients = [
                item for item in self.ingredients_data 
                if filter_text in item['name'].lower()
            ]
        self.update_lists()

    def on_add_clicked(self, widget):
        selection = self.ingredients_view.get_selection()
        model, treeiter = selection.get_selected()
        
        if not treeiter:
            self._show_error("Select an ingredient")
            return
            
        ingredient_name = model.get_value(treeiter, 0)
        gram_text = self.gram_entry.get_text().strip().replace(',', '.')
        
        if not gram_text:
            self._show_error("Enter a weight in grams")
            return
            
        try:
            gram = float(gram_text)
            if gram <= 0:
                raise ValueError
        except ValueError:
            self._show_error("Invalid value - must be a positive number (e.g. 200 or 200.5)")
            return
            
        self.ingredient_name = ingredient_name
        self.gram = gram
        self.response(Gtk.ResponseType.OK)
        self.destroy()

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

class RecipesTab(Gtk.Box):
    def __init__(self, window_width, window_height, parent=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.set_border_width(10)
        self.parent = parent
        self.db_dir = self._get_db_dir()
        self.ingredients_data = []
        self.recipes_data = []
        self.current_recipe = None
        
        self._init_widgets(window_width)
        self._load_ingredients()
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

    def _load_ingredients(self):
        try:
            ingredients_path = os.path.join(self.db_dir, 'ingredients.json')
            with open(ingredients_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.ingredients_data = data['ingredients']
        except Exception as e:
            print(f"Error loading ingredients from {ingredients_path}: {e}")

    def reload_ingredients(self):
        """Reload ingredients data from file and refresh any dependent views"""
        self._load_ingredients()
        # If a recipe is currently loaded, refresh its ingredient data
        if self.current_recipe:
            self._load_recipe_details(self.current_recipe)

    def _load_recipes(self):
        try:
            recipes_path = os.path.join(self.db_dir, 'recipes.json')
            with open(recipes_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.recipes_data = data['recipes']
                self._update_recipe_store()
        except Exception as e:
            print(f"Error loading recipes from {recipes_path}: {e}")

    def _update_recipe_store(self):
        self.recipe_store.clear()
        for recipe in sorted(self.recipes_data, key=lambda x: x['name'].lower()):
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

    def _init_widgets(self, window_width):
        self.recipe_store = Gtk.ListStore(str, float, float, float, float, float, float, float, float, float)
        self.recipe_tree = Gtk.TreeView(model=self.recipe_store)
        self._create_columns(self.recipe_tree, [
            ("Recipe Name", 0.4), ("Gram", 0.07), ("Kcal", 0.07), ("Carbs", 0.07), ("Sugar", 0.07),
            ("Fat", 0.07), ("Protein", 0.07), ("Fiber", 0.07), ("Salt", 0.07), ("Cost", 0.04)
        ], sortable=True)
        
        selection = self.recipe_tree.get_selection()
        selection.set_mode(Gtk.SelectionMode.SINGLE)
        self.recipe_tree.connect("row-activated", self.on_recipe_activated)
        self.recipe_store.set_sort_column_id(0, Gtk.SortType.ASCENDING)

        recipe_scrolled = Gtk.ScrolledWindow()
        recipe_scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        recipe_scrolled.add(self.recipe_tree)
        recipe_frame = Gtk.Frame()
        recipe_frame.add(recipe_scrolled)
        self.pack_start(recipe_frame, True, True, 0)

        button_box = Gtk.Box(spacing=10)
        self.pack_start(button_box, False, False, 0)
        
        self.delete_btn = Gtk.Button(label="Delete Recipe")
        self.new_btn = Gtk.Button(label="New Recipe")
        self.copy_btn = Gtk.Button(label="Copy Recipe")
        self.save_btn = Gtk.Button(label="Save Recipe")
        
        self.delete_btn.connect("clicked", self._on_delete_recipe_clicked)
        self.new_btn.connect("clicked", self._on_new_recipe_clicked)
        self.copy_btn.connect("clicked", self._on_copy_recipe_clicked)
        self.save_btn.connect("clicked", self._on_save_recipe_clicked)
        
        for btn in [self.delete_btn, self.new_btn, self.copy_btn, self.save_btn]:
            button_box.pack_start(btn, True, True, 0)

        self.lower_container = Gtk.HPaned()
        self.lower_container.set_position(int(window_width * 0.618))
        self.lower_container.connect("size-allocate", self._update_paned_position)
        self.pack_start(self.lower_container, True, True, 0)

        self.left_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        
        self.ingredient_store = Gtk.ListStore(str, float, float, float, float, float, float, float, float, float)
        self.ingredient_tree = Gtk.TreeView(model=self.ingredient_store)
        self._create_columns(self.ingredient_tree, [
            ("Ingredient", 0.19), ("Gram", 0.10), ("Kcal", 0.09), ("Carbs", 0.10), ("Sugar", 0.10),
            ("Fat", 0.08), ("Protein", 0.12), ("Fiber", 0.1), ("Salt", 0.08), ("Cost", 0.04)
        ], sortable=True)
        self.ingredient_store.set_sort_column_id(0, Gtk.SortType.ASCENDING)
        self.ingredient_tree.connect("row-activated", self._on_ingredient_row_activated)

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

        control_box = Gtk.Box(spacing=10)
        control_box.set_margin_start(5)
        control_box.set_margin_end(5)
        control_box.set_margin_bottom(5)
        
        self.delete_ingredient_btn = Gtk.Button(label="Delete Ingredient")
        self.delete_ingredient_btn.connect("clicked", self._on_delete_ingredient_clicked)
        control_box.pack_start(self.delete_ingredient_btn, False, False, 0)
        
        self.add_ingredient_btn = Gtk.Button(label="Add Ingredient")
        self.add_ingredient_btn.connect("clicked", self._on_add_ingredient_clicked)
        control_box.pack_end(self.add_ingredient_btn, False, False, 0)
        
        self.left_container.pack_start(control_box, False, False, 0)
        self.lower_container.add1(self.left_container)

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

    def on_recipe_activated(self, treeview, path, column):
        model = treeview.get_model()
        treeiter = model.get_iter(path)
        if treeiter is not None:
            self._load_recipe_details(model[treeiter][0])

    def _load_recipe_details(self, recipe_name):
        self.current_recipe = recipe_name
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

    def _on_ingredient_row_activated(self, treeview, path, column):
        model = treeview.get_model()
        treeiter = model.get_iter(path)
        if treeiter is None:
            return
            
        ingredient_name = model.get_value(treeiter, 0)
        current_gram = model.get_value(treeiter, 1)
        
        dialog = Gtk.Dialog(
            title="Modify Ingredient",
            transient_for=self.get_toplevel(),
            flags=0,
            buttons=("Cancel", Gtk.ResponseType.CANCEL, "OK", Gtk.ResponseType.OK)
        )
        dialog.set_default_size(300, 100)
        
        content_area = dialog.get_content_area()
        content_area.set_margin_start(10)
        content_area.set_margin_end(10)
        content_area.set_margin_top(10)
        content_area.set_margin_bottom(10)
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content_area.pack_start(box, True, True, 0)
        
        label = Gtk.Label(label=f"Modify grams for {ingredient_name}:")
        box.pack_start(label, True, True, 0)
        
        entry = Gtk.Entry()
        entry.set_text(str(current_gram))
        entry.set_activates_default(True)
        box.pack_start(entry, True, True, 0)
        
        dialog.set_default_response(Gtk.ResponseType.OK)
        dialog.show_all()
        
        response = dialog.run()
        new_gram = entry.get_text()
        dialog.destroy()
        
        if response == Gtk.ResponseType.OK and new_gram:
            try:
                new_gram_value = float(new_gram)
                if new_gram_value > 0:
                    ingredient = next((i for i in self.ingredients_data if i['name'] == ingredient_name), None)
                    if ingredient:
                        factor = new_gram_value / 100
                        model.set_value(treeiter, 1, new_gram_value)
                        model.set_value(treeiter, 2, ingredient['kcal'] * factor)
                        model.set_value(treeiter, 3, ingredient['carbs'] * factor)
                        model.set_value(treeiter, 4, ingredient['sugar'] * factor)
                        model.set_value(treeiter, 5, ingredient['fat'] * factor)
                        model.set_value(treeiter, 6, ingredient['protein'] * factor)
                        model.set_value(treeiter, 7, ingredient['fiber'] * factor)
                        model.set_value(treeiter, 8, ingredient['salt'] * factor)
                        model.set_value(treeiter, 9, ingredient['cost'] * factor)
                        self._update_per_portion_values()
                        self._update_current_recipe()
            except ValueError:
                self._show_error("Invalid weight value")

    def _update_current_recipe(self):
        if not self.current_recipe:
            return
            
        recipe = next((r for r in self.recipes_data if r['name'] == self.current_recipe), None)
        if not recipe:
            return
            
        recipe['ingredients'] = []
        for row in self.ingredient_store:
            recipe['ingredients'].append({
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
        
        self._update_recipe_store()

    def _on_add_ingredient_clicked(self, widget):
        dialog = AddIngredientDialog(self.get_toplevel(), self.ingredients_data)
        response = dialog.run()
        
        if response == Gtk.ResponseType.OK:
            ingredient_name = dialog.ingredient_name
            gram = dialog.gram
            
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
            self._update_current_recipe()

    def _on_delete_ingredient_clicked(self, widget):
        selection = self.ingredient_tree.get_selection()
        model, treeiter = selection.get_selected()
        if treeiter is None:
            return
        model.remove(treeiter)
        self._update_per_portion_values()
        self._update_current_recipe()

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
            
        self._save_recipes_to_file()
        self._update_recipe_store()
        self.current_recipe = recipe_name

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
        self.current_recipe = None
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
