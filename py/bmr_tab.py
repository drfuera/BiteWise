import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk
import cairo
import json
import os
import sys
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
        
        # Calculate 7-day moving average of calories
        avg_kcal_values = []
        for i in range(len(kcal_values)):
            start_idx = max(0, i - 6)  # Go back up to 6 days to get 7 days total
            window = kcal_values[start_idx:i+1]
            avg_kcal_values.append(sum(window) / len(window))
        
        if not dates or not bmr_values or not kcal_values:
            self._draw_no_data(cr, width, height, text_color, "Incomplete BMR/Calorie data")
            return
        
        # Calculate min/max values including all PAL levels
        pal_levels = [1.20, 1.35, 1.50, 1.70, 1.85, 2.10, 2.40]
        pal_values = []
        for pal in pal_levels:
            pal_values.extend([bmr * pal for bmr in bmr_values])
            
        min_value = min(min(bmr_values), min(kcal_values), min(avg_kcal_values), min(pal_values)) * 0.95
        max_value = max(max(bmr_values), max(kcal_values), max(avg_kcal_values), max(pal_values)) * 1.05
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
        avg_kcal_color = (1.0, 0.8, 0.0, 1.0)  # Gold color for average
        
        # Draw PAL lines first (so they're behind the main lines)
        pal_colors = [
            (0.2, 0.8, 0.2, 0.3),  # 1.20
            (0.4, 0.8, 0.2, 0.3),   # 1.35
            (0.6, 0.8, 0.2, 0.3),   # 1.50
            (0.8, 0.8, 0.2, 0.3),   # 1.70
            (1.0, 0.6, 0.0, 0.3),   # 1.85
            (1.0, 0.4, 0.0, 0.3),   # 2.10
            (1.0, 0.2, 0.0, 0.3)    # 2.40
        ]
        
        pal_descriptions = [
            "Complete rest (bedridden)",
            "Very low activity (sedentary)",
            "Low activity (office work)",
            "Moderate activity (light exercise)",
            "Active (regular exercise)",
            "Very active (intense exercise)",
            "Extremely active (athlete level)"
        ]
        
        # Store PAL points for each level
        self.pal_points = {}
        for pal, color in zip(pal_levels, pal_colors):
            pal_values = [bmr * pal for bmr in bmr_values]
            points = self._draw_line(cr, dates, pal_values, left_margin, height, bottom_margin, 
                                   graph_width, graph_height, min_value, value_range, color)
            self.pal_points[pal] = points
            
            # Draw points for PAL lines
            if len(dates) <= 100:
                self._draw_points(cr, points, color, radius=3)
        
        # Draw main lines on top
        bmr_points = self._draw_line(cr, dates, bmr_values, left_margin, height, bottom_margin, 
                                   graph_width, graph_height, min_value, value_range, bmr_color)
        kcal_points = self._draw_line(cr, dates, kcal_values, left_margin, height, bottom_margin, 
                                    graph_width, graph_height, min_value, value_range, kcal_color)
        avg_kcal_points = self._draw_line(cr, dates, avg_kcal_values, left_margin, height, bottom_margin,
                                         graph_width, graph_height, min_value, value_range, avg_kcal_color, dash=[5, 3])
        
        if len(dates) <= 100:
            self._draw_points(cr, bmr_points, bmr_color)
            self._draw_points(cr, kcal_points, kcal_color)
            # Don't draw points for average line to keep it clean
        
        if self.hover_point is not None and self.hover_point < len(bmr_points):
            self._draw_highlight(cr, bmr_points[self.hover_point], bmr_color)
            self._draw_highlight(cr, kcal_points[self.hover_point], kcal_color)
            self._draw_highlight(cr, avg_kcal_points[self.hover_point], avg_kcal_color)
            # Highlight all PAL points for this date
            for pal, points in self.pal_points.items():
                if self.hover_point < len(points):
                    self._draw_highlight(cr, points[self.hover_point], pal_colors[pal_levels.index(pal)], radius=5)
        
        self._draw_legend(cr, width, bmr_color, kcal_color, text_color, pal_levels, pal_colors, pal_descriptions, avg_kcal_color)
        
        self.graph_bmr_points = bmr_points
        self.graph_kcal_points = kcal_points
        self.graph_avg_kcal_points = avg_kcal_points
        self.graph_dates = dates
        self.graph_bmr = bmr_values
        self.graph_kcal = kcal_values
        self.graph_avg_kcal = avg_kcal_values
        self.pal_levels = pal_levels
    
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
        title = "BMR vs Calorie Intake (TDEE = BMR × PAL)"
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
    
    def _draw_line(self, cr, dates, values, left_margin, height, bottom_margin, graph_width, graph_height, min_value, value_range, color, dash=None):
        points = []
        cr.set_source_rgba(*color)
        cr.set_line_width(2)
        
        if dash:
            cr.set_dash(dash)
        
        for i, value in enumerate(values):
            x_pos = left_margin + (i * graph_width / max(len(dates) - 1, 1))
            y_pos = height - bottom_margin - ((value - min_value) / value_range * graph_height)
            points.append((x_pos, y_pos))
            
            if i == 0:
                cr.move_to(x_pos, y_pos)
            else:
                cr.line_to(x_pos, y_pos)
        
        cr.stroke()
        if dash:
            cr.set_dash([])  # Reset dash
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
    
    def _draw_legend(self, cr, width, bmr_color, kcal_color, text_color, pal_levels=None, pal_colors=None, pal_descriptions=None, avg_kcal_color=None):
        legend_swatch_size = 12
        legend_swatch_height = 10
        legend_margin = 5
        legend_text_spacing = 5
        legend_item_spacing = 15
        
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(10)
        
        # Main legend (BMR, Calories, and 7-day Average Calories)
        labels = ["BMR", "Calories", "7-day Avg Calories"]
        colors = [bmr_color, kcal_color, avg_kcal_color]
        label_widths = [cr.text_extents(label)[2] for label in labels]
        max_text_height = max(cr.text_extents(label)[3] for label in labels)
        
        # Calculate total width needed for main legend
        total_swatch_width = (legend_swatch_size + legend_text_spacing) * len(labels)
        total_text_width = sum(label_widths) + (legend_item_spacing * (len(labels) - 1))
        total_width = total_swatch_width + total_text_width
        
        legend_x = (width - total_width) / 2
        legend_y = 49
        
        # Draw main legend box
        cr.set_source_rgba(0.2, 0.2, 0.2, 0.8)
        cr.rectangle(legend_x - legend_margin, legend_y - legend_margin, 
                    total_width + 2 * legend_margin, max_text_height + 2 * legend_margin)
        cr.fill()
        
        cr.set_source_rgba(0.8, 0.8, 0.8, 0.8)
        cr.set_line_width(1)
        cr.rectangle(legend_x - legend_margin, legend_y - legend_margin, 
                    total_width + 2 * legend_margin, max_text_height + 2 * legend_margin)
        cr.stroke()
        
        # Draw main legend items
        current_x = legend_x
        for i, (label, color) in enumerate(zip(labels, colors)):
            cr.set_source_rgba(*color)
            if label == "7-day Avg Calories":
                cr.set_line_width(2)
                cr.move_to(current_x, legend_y + legend_swatch_height/2)
                cr.line_to(current_x + legend_swatch_size, legend_y + legend_swatch_height/2)
                cr.stroke()
            else:
                cr.rectangle(current_x, legend_y + 1, legend_swatch_size, legend_swatch_height)
                cr.fill()
            
            cr.set_source_rgba(1, 1, 1, 1)
            cr.move_to(current_x + legend_swatch_size + legend_text_spacing, 
                      legend_y + max_text_height + 1)
            cr.show_text(label)
            
            current_x += legend_swatch_size + legend_text_spacing + label_widths[i] + legend_item_spacing
        
        # PAL legend
        if pal_levels and pal_colors and pal_descriptions:
            cr.set_font_size(9)
            
            # Calculate maximum width needed for PAL legend
            pal_label_widths = []
            max_pal_text_height = 0
            for pal, desc in zip(pal_levels, pal_descriptions):
                label = f"PAL {pal:.2f}: {desc}"
                extents = cr.text_extents(label)
                pal_label_widths.append(extents.width)
                if extents.height > max_pal_text_height:
                    max_pal_text_height = extents.height
            
            max_pal_width = max(pal_label_widths)
            pal_legend_height = (len(pal_levels) * (max_pal_text_height + 5)) + 2 * legend_margin
            
            # Center the PAL legend
            pal_legend_x = (width - (max_pal_width + legend_swatch_size + legend_text_spacing + 2 * legend_margin)) / 2
            pal_legend_y = legend_y + max_text_height + 2 * legend_margin + 20
            
            # Draw PAL legend box
            cr.set_source_rgba(0.2, 0.2, 0.2, 0.8)
            cr.rectangle(pal_legend_x, pal_legend_y - legend_margin, 
                        max_pal_width + legend_swatch_size + legend_text_spacing + 2 * legend_margin,
                        pal_legend_height)
            cr.fill()
            
            cr.set_source_rgba(0.8, 0.8, 0.8, 0.8)
            cr.set_line_width(1)
            cr.rectangle(pal_legend_x, pal_legend_y - legend_margin,
                        max_pal_width + legend_swatch_size + legend_text_spacing + 2 * legend_margin,
                        pal_legend_height)
            cr.stroke()
            
            # Draw PAL legend items
            current_pal_y = pal_legend_y
            for pal, color, desc in zip(pal_levels, pal_colors, pal_descriptions):
                cr.set_source_rgba(*color)
                cr.rectangle(pal_legend_x + legend_margin, current_pal_y, 
                            legend_swatch_size, legend_swatch_height)
                cr.fill()
                
                cr.set_source_rgba(1, 1, 1, 1)
                label = f"PAL {pal:.2f}: {desc}"
                cr.move_to(pal_legend_x + legend_margin + legend_swatch_size + legend_text_spacing, 
                          current_pal_y + max_pal_text_height)
                cr.show_text(label)
                
                current_pal_y += max_pal_text_height + 5

    def on_motion_notify(self, widget, event):
        if not hasattr(self, 'graph_bmr_points') or not hasattr(self, 'graph_kcal_points'):
            return False
            
        closest_point = None
        min_dist = float('inf')
        
        # Check all points (BMR, Calories, and PAL levels)
        all_points = []
        all_points.extend(self.graph_bmr_points)
        all_points.extend(self.graph_kcal_points)
        all_points.extend(self.graph_avg_kcal_points)
        for pal_points in self.pal_points.values():
            all_points.extend(pal_points)
        
        for i, point in enumerate(all_points):
            dist = ((point[0] - event.x) ** 2 + (point[1] - event.y) ** 2) ** 0.5
            if dist < min_dist and dist < 20:
                min_dist = dist
                closest_point = i % len(self.graph_bmr_points)  # Map back to date index
        
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
        avg_kcal = self.graph_avg_kcal[self.hover_point]
        weight = next((e.get('weight') for e in self.journal_data if e.get('date') == date), None)
        
        try:
            date_str = datetime.strptime(date, "%Y-%m-%d").strftime("%B %d, %Y")
        except:
            date_str = date
        
        # Calculate PAL comparisons
        pal_comparisons = []
        for pal in self.pal_levels:
            pal_value = bmr * pal
            if pal_value == 0:  # Avoid division by zero
                continue
            percentage = ((kcal - pal_value) / pal_value) * 100
            if percentage > 0:
                comparison = f"+{percentage:.1f}% above"
            else:
                comparison = f"{percentage:.1f}% below"
            pal_comparisons.append(f"PAL {pal:.2f}: {pal_value:.0f} kcal ({comparison})")
        
        tooltip_text = (f"<b>{date_str}</b>\n" + 
                       (f"Weight: {weight} kg\n" if weight else "") +
                       f"BMR: {bmr:.0f} kcal\n" +
                       f"Calories: {kcal:.0f} kcal\n" +
                       f"7-day Avg Calories: {avg_kcal:.0f} kcal\n\n" +
                       "\n".join(pal_comparisons))
        tooltip.set_markup(tooltip_text)
        return True

class BMRStatsTab(Gtk.Box):
    def __init__(self, window_width, window_height):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_border_width(10)
        
        self.db_dir = self._get_db_dir()
        self.journal_data = self._load_journal_data()
        self.diet_data = self._load_diet_data()
        self.bmr_kcal_data = self._process_bmr_kcal_data()
        
        self.create_bmr_kcal_plot()

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

    def _load_journal_data(self):
        try:
            journal_path = os.path.join(self.db_dir, 'journal.json')
            with open(journal_path, 'r', encoding='utf-8') as f:
                data = json.load(f).get('entries', [])
                return [entry for entry in data if entry.get('date') and entry.get('weight')]
        except Exception as e:
            print(f"Error loading journal data: {e}")
            return []

    def _load_diet_data(self):
        try:
            diet_path = os.path.join(self.db_dir, 'diet.json')
            with open(diet_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
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
