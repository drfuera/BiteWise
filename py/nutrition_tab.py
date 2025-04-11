import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GObject, Pango
import cairo
import json
import os
import sys
from datetime import datetime
from collections import OrderedDict

class NutrientGraph(Gtk.DrawingArea):
    def __init__(self, nutrient_data):
        super().__init__()
        self.nutrient_data = nutrient_data
        self.hover_point = None
        self.set_hexpand(True)
        self.set_vexpand(True)
        
        # Event setup
        self.set_has_tooltip(True)
        self.add_events(Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.connect("draw", self.on_draw)
        self.connect("query-tooltip", self.on_query_tooltip)
        self.connect("motion-notify-event", self.on_motion_notify)
        self.connect("leave-notify-event", self.on_leave_notify)

    def on_draw(self, widget, cr):
        width, height = widget.get_allocated_width(), widget.get_allocated_height()
        style_context = widget.get_style_context()
        bg_color = style_context.get_background_color(Gtk.StateFlags.NORMAL)
        text_color = style_context.get_color(Gtk.StateFlags.NORMAL)
        
        # Draw background
        cr.set_source_rgba(bg_color.red, bg_color.green, bg_color.blue, bg_color.alpha)
        cr.rectangle(0, 0, width, height)
        cr.fill()
        
        if not self.nutrient_data:
            self._draw_no_data_message(cr, width, height, text_color)
            return
        
        # Graph configuration - nutrients now in desired stacking order
        nutrients = ['protein', 'carbs', 'sugar', 'fat', 'fiber', 'salt']
        colors = [
            (1.0, 0.8, 0.6, 1.0),  # protein
            (0.4, 0.7, 1.0, 1.0),  # carbs
            (0.6, 1.0, 0.6, 1.0),   # sugar
            (1.0, 0.6, 0.6, 1.0),   # fat
            (0.8, 0.6, 1.0, 1.0),   # fiber
            (0.6, 0.8, 1.0, 1.0)    # salt
        ]
        
        # Calculate max value with 10% headroom
        max_value = max(sum(values.values()) for values in self.nutrient_data.values()) * 1.1
        
        # Graph dimensions
        left_margin, right_margin, top_margin, bottom_margin = 60, 60, 80, 60
        graph_width = max(width - left_margin - right_margin, 1)
        graph_height = max(height - top_margin - bottom_margin, 1)
        
        # Draw axes and labels
        self._draw_axes(cr, width, height, left_margin, right_margin, top_margin, bottom_margin, text_color)
        self._draw_y_labels(cr, width, height, left_margin, right_margin, bottom_margin, graph_height, max_value, text_color)
        self._draw_x_labels(cr, width, height, left_margin, bottom_margin, graph_width, text_color)
        
        # Draw bars
        self.bar_rects = self._draw_bars(
            cr, nutrients, colors, width, height, 
            left_margin, bottom_margin, graph_width, graph_height, 
            max_value, text_color
        )
        
        # Draw title and legend
        self._draw_title(cr, width, text_color)
        self._draw_legend(cr, width, nutrients, colors, text_color)

    def _draw_no_data_message(self, cr, width, height, text_color):
        cr.set_source_rgba(text_color.red, text_color.green, text_color.blue, text_color.alpha)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(14)
        text = "No nutrient data available"
        extents = cr.text_extents(text)
        cr.move_to(width/2 - extents[2]/2, height/2 - extents[3]/2)
        cr.show_text(text)

    def _draw_axes(self, cr, width, height, left_margin, right_margin, top_margin, bottom_margin, text_color):
        cr.set_source_rgba(text_color.red, text_color.green, text_color.blue, 0.5)
        cr.set_line_width(1)
        cr.move_to(left_margin, height - bottom_margin)
        cr.line_to(width - right_margin, height - bottom_margin)
        cr.stroke()
        cr.move_to(left_margin, top_margin)
        cr.line_to(left_margin, height - bottom_margin)
        cr.stroke()

    def _draw_y_labels(self, cr, width, height, left_margin, right_margin, bottom_margin, graph_height, max_value, text_color):
        cr.set_source_rgba(text_color.red, text_color.green, text_color.blue, text_color.alpha)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(10)
        
        for i in range(6):  # 5 ticks + 1
            y_pos = height - bottom_margin - (i * graph_height / 5)
            value = i * max_value / 5
            label = f"{value:.0f}g"
            extents = cr.text_extents(label)
            cr.move_to(left_margin - extents[2] - 5, y_pos + extents[3]/2)
            cr.show_text(label)
            
            cr.set_source_rgba(text_color.red, text_color.green, text_color.blue, 0.2)
            cr.set_line_width(0.5)
            cr.move_to(left_margin, y_pos)
            cr.line_to(width - right_margin, y_pos)
            cr.stroke()
            cr.set_source_rgba(text_color.red, text_color.green, text_color.blue, text_color.alpha)

    def _draw_x_labels(self, cr, width, height, left_margin, bottom_margin, graph_width, text_color):
        dates = sorted(self.nutrient_data.keys())
        cr.set_font_size(10)
        step = max(1, len(dates) // 10)
        
        for i in range(0, len(dates), step):
            if i >= len(dates):
                continue
            date_str = dates[i]
            try:
                label = datetime.strptime(date_str, "%Y-%m-%d").strftime("%b %d")
            except:
                label = date_str
            x_pos = left_margin + (i * graph_width / max(len(dates) - 1, 1))
            extents = cr.text_extents(label)
            cr.move_to(x_pos - extents[2]/2, height - bottom_margin + extents[3] + 5)
            cr.show_text(label)

    def _draw_bars(self, cr, nutrients, colors, width, height, left_margin, bottom_margin, 
                  graph_width, graph_height, max_value, text_color):
        dates = sorted(self.nutrient_data.keys())
        num_dates = len(dates)
        bar_width = 40 if num_dates <= 1 else min(30, graph_width / num_dates)
        bar_spacing = 0 if num_dates <= 1 else (graph_width - (num_dates * bar_width)) / (num_dates - 1)
        
        bar_rects = []
        for i, date in enumerate(dates):
            x_pos = left_margin + (graph_width / 2 if num_dates == 1 else 
                                (i * (bar_width + bar_spacing)) + (bar_width / 2))
            bottom_y = height - bottom_margin
            current_bottom = bottom_y
            bar_rects_for_date = []
            
            # Draw nutrients in reverse order so first in list is on top
            for j, nutrient in enumerate(reversed(nutrients)):
                value = self.nutrient_data[date][nutrient]
                if value <= 0:
                    continue
                    
                bar_height = (value / max_value) * graph_height
                y_pos = current_bottom - bar_height
                is_hovered = (self.hover_point is not None and 
                             self.hover_point[0] == i and 
                             self.hover_point[1] == nutrient)
                
                # Draw bar
                color_idx = nutrients.index(nutrient)
                r, g, b, a = colors[color_idx]
                if is_hovered:
                    cr.set_source_rgba(min(1.0, r + 0.2), min(1.0, g + 0.2), min(1.0, b + 0.2), a)
                else:
                    cr.set_source_rgba(r, g, b, a)
                cr.rectangle(x_pos - bar_width/2, y_pos, bar_width, bar_height)
                cr.fill()
                
                # Add border for hovered segment
                if is_hovered:
                    cr.set_source_rgba(1, 1, 1, 0.8)
                    cr.set_line_width(1.5)
                    cr.rectangle(x_pos - bar_width/2, y_pos, bar_width, bar_height)
                    cr.stroke()
                
                bar_rects_for_date.append({
                    'nutrient': nutrient,
                    'rect': (x_pos - bar_width/2, y_pos, bar_width, bar_height),
                    'value': value
                })
                current_bottom = y_pos
            
            bar_rects.append({
                'date': date,
                'rects': bar_rects_for_date,
                'x_pos': x_pos - bar_width/2,
                'width': bar_width
            })
        return bar_rects

    def _draw_title(self, cr, width, text_color):
        cr.set_source_rgba(text_color.red, text_color.green, text_color.blue, text_color.alpha)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(14)
        title = "Daily Nutrient Intake"
        extents = cr.text_extents(title)
        cr.move_to(width/2 - extents[2]/2, 30)
        cr.show_text(title)

    def _draw_legend(self, cr, width, nutrients, colors, text_color):
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(10)
        
        # Calculate text dimensions
        nutrient_widths = [cr.text_extents(n.capitalize())[2] for n in nutrients]
        max_text_height = max(cr.text_extents(n.capitalize())[3] for n in nutrients)
        
        # Calculate total legend width
        swatch_size, text_spacing, item_spacing = 12, 5, 5
        total_width = sum(swatch_size + text_spacing + w + item_spacing for w in nutrient_widths) - item_spacing
        
        # Position legend
        margin = 5
        legend_x, legend_y = (width - total_width) / 2, 49
        
        # Draw legend background
        cr.set_source_rgba(0.2, 0.2, 0.2, 0.8)
        cr.rectangle(legend_x - margin, legend_y - margin, 
                    total_width + 2 * margin, max_text_height + 2 * margin)
        cr.fill()
        cr.set_source_rgba(0.8, 0.8, 0.8, 0.8)
        cr.set_line_width(1)
        cr.stroke()
        
        # Draw legend items
        current_x = legend_x
        for i, (nutrient, color) in enumerate(zip(nutrients, colors)):
            cr.set_source_rgba(*color)
            cr.rectangle(current_x, legend_y + 1, swatch_size, 10)
            cr.fill()
            
            cr.set_source_rgba(1, 1, 1, 1)
            cr.move_to(current_x + swatch_size + text_spacing, legend_y + max_text_height + 1)
            cr.show_text(nutrient.capitalize())
            
            current_x += swatch_size + text_spacing + nutrient_widths[i] + item_spacing

    def on_motion_notify(self, widget, event):
        if not hasattr(self, 'bar_rects'):
            return False
        
        for date_idx, date_data in enumerate(self.bar_rects):
            x_pos, width = date_data['x_pos'], date_data['width']
            if x_pos <= event.x <= x_pos + width:
                for rect_data in date_data['rects']:
                    rx, ry, rw, rh = rect_data['rect']
                    if ry <= event.y <= ry + rh:
                        if self.hover_point != (date_idx, rect_data['nutrient']):
                            self.hover_point = (date_idx, rect_data['nutrient'])
                            self.queue_draw()
                        return True
        if self.hover_point is not None:
            self.hover_point = None
            self.queue_draw()
        return False
    
    def on_leave_notify(self, widget, event):
        if self.hover_point is not None:
            self.hover_point = None
            self.queue_draw()
    
    def on_query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        if not hasattr(self, 'bar_rects') or self.hover_point is None:
            return False
        
        date_idx, nutrient = self.hover_point
        date = self.bar_rects[date_idx]['date']
        value = next(r['value'] for r in self.bar_rects[date_idx]['rects'] if r['nutrient'] == nutrient)
        
        try:
            date_str = datetime.strptime(date, "%Y-%m-%d").strftime("%B %d, %Y")
        except:
            date_str = date
        
        tooltip.set_markup(f"<b>{date_str}</b>\n{nutrient.capitalize()}: {value:.1f}g")
        return True

class NutritionTab(Gtk.Box):
    def __init__(self, window_width, window_height):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_border_width(10)
        self.db_dir = self._get_db_dir()
        self._load_and_process_data()
        self.create_nutrient_plot()

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

    def _load_and_process_data(self):
        try:
            journal_path = os.path.join(self.db_dir, 'journal.json')
            with open(journal_path, 'r', encoding='utf-8') as f:
                entries = json.load(f).get('entries', [])
        except Exception as e:
            print(f"Error loading journal data: {e}")
            entries = []
        
        self.nutrient_data = OrderedDict()
        for entry in entries:
            if not entry.get('date'):
                continue
            date = entry['date']
            if date not in self.nutrient_data:
                self.nutrient_data[date] = {n: 0.0 for n in ['protein', 'carbs', 'sugar', 'fat', 'fiber', 'salt']}
            for nutrient in self.nutrient_data[date]:
                self.nutrient_data[date][nutrient] += entry.get(nutrient, 0)

    def create_nutrient_plot(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        scrolled.add(box)
        
        if not self.nutrient_data:
            box.pack_start(Gtk.Label(label="No nutrient data available"), True, True, 0)
        else:
            box.pack_start(NutrientGraph(self.nutrient_data), True, True, 0)
        
        self.pack_start(scrolled, True, True, 0)

    def update_nutrient_plot(self):
        self._load_and_process_data()
        for child in self.get_children():
            self.remove(child)
        self.create_nutrient_plot()
        self.show_all()
