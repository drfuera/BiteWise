import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk
import cairo
import json
import os
from datetime import datetime
from collections import OrderedDict
from math import pi
from .diet_guidelines import calculate_bmr

class BMRGraph(Gtk.DrawingArea):
    def __init__(self, bmr_kcal_data, journal_data):
        super().__init__()
        self.bmr_kcal_data = bmr_kcal_data
        self.journal_data = journal_data
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.connect("draw", self.on_draw)
        
        self.hover_point = None
        self.set_has_tooltip(True)
        self.connect("query-tooltip", self.on_query_tooltip)
        
        self.add_events(Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.connect("motion-notify-event", self.on_motion_notify)
        self.connect("leave-notify-event", self.on_leave_notify)

    def on_draw(self, widget, cr):
        width, height = widget.get_allocated_width(), widget.get_allocated_height()
        style_context = widget.get_style_context()
        bg_color = style_context.get_background_color(Gtk.StateFlags.NORMAL)
        text_color = style_context.get_color(Gtk.StateFlags.NORMAL)
        
        cr.set_source_rgba(bg_color.red, bg_color.green, bg_color.blue, bg_color.alpha)
        cr.rectangle(0, 0, width, height)
        cr.fill()
        
        if not self.bmr_kcal_data:
            self._draw_no_data(cr, width, height, text_color)
            return
            
        dates = sorted(self.bmr_kcal_data.keys())
        bmr_values = [self.bmr_kcal_data[d]['bmr'] for d in dates]
        kcal_values = [self.bmr_kcal_data[d]['kcal'] for d in dates]
        
        if not dates or not bmr_values or not kcal_values:
            self._draw_no_data(cr, width, height, text_color, "Incomplete BMR/Calorie data")
            return
            
        min_value = min(min(bmr_values), min(kcal_values)) * 0.95
        max_value = max(max(bmr_values), max(kcal_values)) * 1.05
        value_range = max_value - min_value if max_value != min_value else max_value or 1
        
        left_margin, right_margin = 60, 60
        top_margin, bottom_margin = 80, 60
        graph_width = max(width - left_margin - right_margin, 1)
        graph_height = max(height - top_margin - bottom_margin, 1)
        
        self._draw_title(cr, width, text_color)
        self._draw_axes(cr, width, height, left_margin, right_margin, top_margin, bottom_margin, text_color)
        self._draw_y_labels(cr, height, left_margin, bottom_margin, graph_height, graph_width, min_value, value_range, text_color)
        self._draw_x_labels(cr, width, height, left_margin, bottom_margin, graph_width, dates, text_color)
        
        bmr_color = (0.4, 0.7, 1.0, 1.0)
        kcal_color = (1.0, 0.5, 0.0, 1.0)
        
        bmr_points = self._draw_line(cr, dates, bmr_values, left_margin, height, bottom_margin, graph_width, 
                                   graph_height, min_value, value_range, bmr_color)
        kcal_points = self._draw_line(cr, dates, kcal_values, left_margin, height, bottom_margin, graph_width, 
                                    graph_height, min_value, value_range, kcal_color)
        
        if len(dates) <= 100:
            self._draw_points(cr, bmr_points, bmr_color)
            self._draw_points(cr, kcal_points, kcal_color)
        
        if self.hover_point is not None and self.hover_point < len(bmr_points):
            self._draw_highlight(cr, bmr_points[self.hover_point], bmr_color)
            self._draw_highlight(cr, kcal_points[self.hover_point], kcal_color)
        
        self._draw_legend(cr, width, bmr_color, kcal_color, text_color)
        
        self.graph_bmr_points = bmr_points
        self.graph_kcal_points = kcal_points
        self.graph_dates = dates
        self.graph_bmr = bmr_values
        self.graph_kcal = kcal_values
    
    def _draw_no_data(self, cr, width, height, text_color, text="No BMR/Calorie data available"):
        cr.set_source_rgba(text_color.red, text_color.green, text_color.blue, text_color.alpha)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(14)
        extents = cr.text_extents(text)
        cr.move_to(width/2 - extents.width/2, height/2 - extents.height/2)
        cr.show_text(text)
    
    def _draw_title(self, cr, width, text_color):
        cr.set_source_rgba(text_color.red, text_color.green, text_color.blue, text_color.alpha)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(14)
        title = "BMR vs Calorie Intake"
        extents = cr.text_extents(title)
        cr.move_to(width/2 - extents.width/2, 30)
        cr.show_text(title)
    
    def _draw_axes(self, cr, width, height, left_margin, right_margin, top_margin, bottom_margin, text_color):
        cr.set_source_rgba(text_color.red, text_color.green, text_color.blue, 0.5)
        cr.set_line_width(1)
        cr.move_to(left_margin, height - bottom_margin)
        cr.line_to(width - right_margin, height - bottom_margin)
        cr.stroke()
        cr.move_to(left_margin, top_margin)
        cr.line_to(left_margin, height - bottom_margin)
        cr.stroke()
    
    def _draw_y_labels(self, cr, height, left_margin, bottom_margin, graph_height, graph_width, min_value, value_range, text_color):
        cr.set_source_rgba(text_color.red, text_color.green, text_color.blue, text_color.alpha)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(10)
        
        num_y_ticks = 5
        for i in range(num_y_ticks + 1):
            y_pos = height - bottom_margin - (i * graph_height / num_y_ticks)
            value = min_value + (i * value_range / num_y_ticks)
            label = f"{value:.0f}"
            extents = cr.text_extents(label)
            cr.move_to(left_margin - extents.width - 5, y_pos + extents.height/2)
            cr.show_text(label)
            
            cr.set_source_rgba(text_color.red, text_color.green, text_color.blue, 0.2)
            cr.set_line_width(0.5)
            cr.move_to(left_margin, y_pos)
            cr.line_to(left_margin + graph_width, y_pos)
            cr.stroke()
            cr.set_source_rgba(text_color.red, text_color.green, text_color.blue, text_color.alpha)
    
    def _draw_x_labels(self, cr, width, height, left_margin, bottom_margin, graph_width, dates, text_color):
        cr.set_font_size(10)
        num_dates = len(dates)
        step = max(1, num_dates // 10)
        
        for i in range(0, num_dates, step):
            if i >= num_dates:
                continue
                
            date_str = dates[i]
            try:
                label = datetime.strptime(date_str, "%Y-%m-%d").strftime("%b %d")
            except:
                label = date_str
            
            x_pos = left_margin + (i * graph_width / max(num_dates - 1, 1))
            extents = cr.text_extents(label)
            cr.move_to(x_pos - extents.width/2, height - bottom_margin + extents.height + 5)
            cr.show_text(label)
    
    def _draw_line(self, cr, dates, values, left_margin, height, bottom_margin, graph_width, graph_height, min_value, value_range, color):
        points = []
        cr.set_source_rgba(*color)
        cr.set_line_width(2)
        
        for i, value in enumerate(values):
            x_pos = left_margin + (i * graph_width / max(len(dates) - 1, 1))
            y_pos = height - bottom_margin - ((value - min_value) / value_range * graph_height)
            points.append((x_pos, y_pos))
            
            if i == 0:
                cr.move_to(x_pos, y_pos)
            else:
                cr.line_to(x_pos, y_pos)
        
        cr.stroke()
        return points
    
    def _draw_points(self, cr, points, color, radius=5):
        cr.set_source_rgba(*color)
        for x_pos, y_pos in points:
            cr.arc(x_pos, y_pos, radius, 0, 2 * pi)
            cr.fill()
    
    def _draw_highlight(self, cr, point, color, radius=7):
        cr.set_source_rgba(*color[:3], 0.8)
        cr.arc(point[0], point[1], radius, 0, 2 * pi)
        cr.fill()
    
    def _draw_legend(self, cr, width, bmr_color, kcal_color, text_color):
        legend_swatch_size, legend_swatch_height = 12, 10
        legend_padding, legend_margin = 8, 5
        legend_text_spacing, legend_item_spacing = 5, 5
        
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(10)
        
        labels = ["BMR", "Calories"]
        label_widths = [cr.text_extents(label)[2] for label in labels]
        max_text_height = max(cr.text_extents(label)[3] for label in labels)
        
        total_width = (legend_swatch_size + legend_text_spacing) * 2 + sum(label_widths) + legend_item_spacing
        legend_x = (width - total_width) / 2
        legend_y = 49
        
        cr.set_source_rgba(0.2, 0.2, 0.2, 0.8)
        cr.rectangle(legend_x - legend_margin, legend_y - legend_margin, 
                    total_width + 2 * legend_margin, max_text_height + 2 * legend_margin)
        cr.fill()
        
        cr.set_source_rgba(0.8, 0.8, 0.8, 0.8)
        cr.set_line_width(1)
        cr.rectangle(legend_x - legend_margin, legend_y - legend_margin, 
                    total_width + 2 * legend_margin, max_text_height + 2 * legend_margin)
        cr.stroke()
        
        current_x = legend_x
        for i, (label, color) in enumerate(zip(labels, [bmr_color, kcal_color])):
            cr.set_source_rgba(*color)
            cr.rectangle(current_x, legend_y + 1, legend_swatch_size, legend_swatch_height)
            cr.fill()
            
            cr.set_source_rgba(1, 1, 1, 1)
            cr.move_to(current_x + legend_swatch_size + legend_text_spacing, 
                      legend_y + max_text_height + 1)
            cr.show_text(label)
            
            current_x += legend_swatch_size + legend_text_spacing + label_widths[i] + legend_item_spacing

    def on_motion_notify(self, widget, event):
        if not hasattr(self, 'graph_bmr_points') or not hasattr(self, 'graph_kcal_points'):
            return False
            
        closest_point = None
        min_dist = float('inf')
        
        # Check both BMR and kcal points for closest hover
        for i, (bmr_point, kcal_point) in enumerate(zip(self.graph_bmr_points, self.graph_kcal_points)):
            # Calculate distance to both points and take the minimum
            bmr_dist = ((bmr_point[0] - event.x) ** 2 + (bmr_point[1] - event.y) ** 2) ** 0.5
            kcal_dist = ((kcal_point[0] - event.x) ** 2 + (kcal_point[1] - event.y) ** 2) ** 0.5
            dist = min(bmr_dist, kcal_dist)
            
            if dist < min_dist and dist < 20:
                min_dist = dist
                closest_point = i
        
        if closest_point != self.hover_point:
            self.hover_point = closest_point
            self.queue_draw()
            return True
        return False
    
    def on_leave_notify(self, widget, event):
        if self.hover_point is not None:
            self.hover_point = None
            self.queue_draw()
    
    def on_query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        if not hasattr(self, 'graph_bmr_points') or self.hover_point is None:
            return False
        
        date = self.graph_dates[self.hover_point]
        bmr = self.graph_bmr[self.hover_point]
        kcal = self.graph_kcal[self.hover_point]
        weight = next((e.get('weight') for e in self.journal_data if e.get('date') == date), None)
        
        try:
            date_str = datetime.strptime(date, "%Y-%m-%d").strftime("%B %d, %Y")
        except:
            date_str = date
        
        tooltip_text = (f"<b>{date_str}</b>\n" + 
                       (f"Weight: {weight} kg\n" if weight else "") +
                       f"BMR: {bmr:.0f} kcal\nCalories: {kcal:.0f} kcal")
        tooltip.set_markup(tooltip_text)
        return True

class BMRStatsTab(Gtk.Box):
    def __init__(self, window_width, window_height):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_border_width(10)
        
        # Initialize data first
        self.journal_data = self._load_journal_data()
        self.diet_data = self._load_diet_data()
        self.bmr_kcal_data = self._process_bmr_kcal_data()
        
        # Then create the plot
        self.create_bmr_kcal_plot()

    def _load_journal_data(self):
        try:
            journal_path = os.path.join(os.path.dirname(__file__), '../db/journal.json')
            with open(journal_path, 'r', encoding='utf-8') as f:
                data = json.load(f).get('entries', [])
                # Ensure entries have dates and weights
                return [entry for entry in data if entry.get('date') and entry.get('weight')]
        except Exception as e:
            print(f"Error loading journal data: {e}")
            return []

    def _load_diet_data(self):
        try:
            diet_path = os.path.join(os.path.dirname(__file__), '../db/diet.json')
            with open(diet_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Verify required fields exist
                if all(k in data for k in ['date_of_birth', 'height_cm', 'gender']):
                    return data
                return {}
        except Exception as e:
            print(f"Error loading diet data: {e}")
            return {}

    def _process_bmr_kcal_data(self):
        if not self.journal_data or not self.diet_data:
            return None
            
        daily_data = OrderedDict()
        for entry in self.journal_data:
            date = entry.get('date')
            weight = entry.get('weight', 0)
            if not date or weight <= 0:
                continue
                
            if date not in daily_data:
                daily_data[date] = {'kcal': 0.0, 'weight': weight}
            daily_data[date]['kcal'] += entry.get('kcal', 0)
        
        bmr_kcal_data = OrderedDict()
        for date, values in sorted(daily_data.items()):
            kcal = values['kcal']
            weight = values['weight']
            bmr = 0
            
            try:
                dob = self.diet_data['date_of_birth']
                height = self.diet_data['height_cm']
                gender = self.diet_data['gender']
                age = datetime.now().year - int(dob[:4])
                bmr = calculate_bmr(gender, weight, height, age)
            except Exception as e:
                print(f"BMR calculation error: {e}")
                continue
            
            bmr_kcal_data[date] = {'bmr': bmr, 'kcal': kcal}
        
        return bmr_kcal_data if bmr_kcal_data else None

    def create_bmr_kcal_plot(self):
        for child in self.get_children():
            self.remove(child)
        
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        scrolled.add(box)
        
        if not self.bmr_kcal_data:
            label = Gtk.Label(label="No BMR data available. Ensure you have:\n"
                                  "- Journal entries with dates and weights\n"
                                  "- Complete diet settings (birth date, height, gender)")
            label.set_line_wrap(True)
            label.set_justify(Gtk.Justification.CENTER)
            box.pack_start(label, True, True, 0)
        else:
            box.pack_start(BMRGraph(self.bmr_kcal_data, self.journal_data), True, True, 0)
        
        self.pack_start(scrolled, True, True, 0)
        self.show_all()

    def update_bmr_plot(self):
        self.journal_data = self._load_journal_data()
        self.diet_data = self._load_diet_data()
        self.bmr_kcal_data = self._process_bmr_kcal_data()
        self.create_bmr_kcal_plot()
