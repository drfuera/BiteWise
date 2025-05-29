import os
import json
import sys
from datetime import datetime, timedelta
from collections import defaultdict
from math import pi
import gi
from gi.repository import Gtk, Gdk, GObject
import cairo

gi.require_version("Gtk", "3.0")

class TimelineVisualizer:
    def __init__(self):
        self.meal_colors = {
            'breakfast': (1.0, 0.8, 0.2),  # Golden yellow
            'lunch': (0.2, 0.8, 0.4),      # Green
            'dinner': (0.8, 0.3, 0.3),     # Red
            'snack': (0.6, 0.4, 1.0),      # Purple
            'late_night': (0.4, 0.4, 0.4)  # Gray
        }

    def get_meal_category(self, hour):
        """Categorize meal based on time of day"""
        if 5 <= hour < 11: return 'breakfast'
        elif 11 <= hour < 16: return 'lunch'
        elif 16 <= hour < 21: return 'dinner'
        elif 21 <= hour < 24 or hour < 5: return 'late_night'
        return 'snack'

    def generate_date_range(self, days):
        """Generate complete date range including today"""
        today = datetime.now().date()
        return [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in reversed(range(days))]

    def process_journal_data(self, journal_data):
        """Organize journal entries by date"""
        timeline_data = defaultdict(list)
        for entry in journal_data:
            if isinstance(entry, dict) and entry.get('date') and entry.get('timestamp'):
                timeline_data[entry['date']].append(entry)
        
        # Sort entries by timestamp within each date
        for date in timeline_data:
            timeline_data[date].sort(key=lambda x: x.get('timestamp', ''))
        
        return timeline_data

    @staticmethod
    def escape_markup(text):
        """Escape special characters for Pango markup"""
        if not text:
            return ""
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

class TimelineGraph(Gtk.DrawingArea):
    def __init__(self, timeline_data, days=30):
        super().__init__()
        self.visualizer = TimelineVisualizer()
        self.timeline_data = timeline_data
        self.days = days
        
        # Setup drawing area
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.connect("draw", self.on_draw)
        
        # Setup hover interaction
        self.hover_meal = None
        self.meal_circles = []
        self.set_has_tooltip(True)
        self.connect("query-tooltip", self.on_query_tooltip)
        self.add_events(Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.connect("motion-notify-event", self.on_motion_notify)
        self.connect("leave-notify-event", self.on_leave_notify)

    def on_draw(self, widget, cr):
        width, height = widget.get_allocated_width(), widget.get_allocated_height()
        
        # Setup background
        style_context = widget.get_style_context()
        bg_color = style_context.get_background_color(Gtk.StateFlags.NORMAL)
        text_color = style_context.get_color(Gtk.StateFlags.NORMAL)
        
        cr.set_source_rgba(bg_color.red, bg_color.green, bg_color.blue, bg_color.alpha)
        cr.rectangle(0, 0, width, height)
        cr.fill()
        
        if not self.timeline_data:
            self.draw_no_data_message(cr, width, height, text_color)
            return
        
        # Layout parameters with padding to keep circles inside
        left_margin, right_margin = 80, 20
        top_margin, bottom_margin = 90, 60  # Increased top margin for legend
        graph_width = max(width - left_margin - right_margin - 20, 1)
        graph_height = max(height - top_margin - bottom_margin - 20, 1)
        
        # Get complete date range
        date_range = self.visualizer.generate_date_range(self.days)
        
        # Draw components
        self.draw_title(cr, width, text_color)
        self.draw_legend(cr, width, text_color)
        self.draw_axes(cr, width, height, left_margin, right_margin,
                      top_margin, bottom_margin, graph_width, graph_height,
                      text_color, date_range)
        self.draw_no_data_indicators(cr, date_range, left_margin, top_margin, graph_width, graph_height, text_color)
        self.draw_meals(cr, date_range, left_margin, top_margin,
                       graph_width, graph_height)

    def draw_no_data_message(self, cr, width, height, text_color):
        cr.set_source_rgba(text_color.red, text_color.green, text_color.blue, text_color.alpha)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(14)
        text = "No timeline data available"
        extents = cr.text_extents(text)
        cr.move_to(width/2 - extents.width/2, height/2)
        cr.show_text(text)

    def draw_title(self, cr, width, text_color):
        cr.set_source_rgba(text_color.red, text_color.green, text_color.blue, text_color.alpha)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(16)
        title = f"Eating Timeline - Last {self.days} Days"
        extents = cr.text_extents(title)
        cr.move_to(width/2 - extents.width/2, 30)
        cr.show_text(title)

    def draw_legend(self, cr, width, text_color):
        legend_items = [
            ('Breakfast (5-11h)', self.visualizer.meal_colors['breakfast']),
            ('Lunch (11-16h)', self.visualizer.meal_colors['lunch']),
            ('Dinner (16-21h)', self.visualizer.meal_colors['dinner']),
            ('Late Night (21-5h)', self.visualizer.meal_colors['late_night'])
        ]
        
        cr.set_font_size(10)
        legend_y = 60  # Positioned at top
        total_width = sum(cr.text_extents(item[0])[2] + 25 for item in legend_items)
        start_x = (width - total_width) / 2
        
        # Legend background - matching nutrition script style
        cr.set_source_rgba(0.2, 0.2, 0.2, 0.8)
        margin = 5
        max_text_height = max(cr.text_extents(item[0])[3] for item in legend_items)
        cr.rectangle(start_x - margin, legend_y - margin, 
                    total_width + 2 * margin, max_text_height + 2 * margin)
        cr.fill()
        cr.set_source_rgba(0.8, 0.8, 0.8, 0.8)
        cr.set_line_width(1)
        cr.stroke()
        
        current_x = start_x
        for label, color in legend_items:
            # Color dot
            cr.set_source_rgba(*color, 0.8)
            cr.arc(current_x + 6, legend_y + 6, 4, 0, 2 * pi)
            cr.fill()
            
            # Label text
            cr.set_source_rgba(1, 1, 1, 1)
            cr.move_to(current_x + 15, legend_y + max_text_height + 1)
            cr.show_text(label)
            current_x += cr.text_extents(label)[2] + 25

    def draw_axes(self, cr, width, height, left_margin, right_margin,
                 top_margin, bottom_margin, graph_width, graph_height,
                 text_color, date_range):
        # Vertical time axis
        cr.set_source_rgba(text_color.red, text_color.green, text_color.blue, 0.5)
        cr.set_line_width(1)
        cr.move_to(left_margin, top_margin)
        cr.line_to(left_margin, top_margin + graph_height)
        cr.stroke()
        
        # Horizontal date axis
        cr.move_to(left_margin, top_margin + graph_height)
        cr.line_to(left_margin + graph_width, top_margin + graph_height)
        cr.stroke()
        
        # Time labels and grid lines (flipped to have 00:00 at bottom)
        cr.set_font_size(10)
        for hour in range(0, 24, 3):
            # Flip the y-position calculation
            y_pos = top_margin + graph_height - (hour / 23) * graph_height
            time_str = f"{hour:02d}:00"
            extents = cr.text_extents(time_str)
            cr.set_source_rgba(text_color.red, text_color.green, text_color.blue, text_color.alpha)
            cr.move_to(left_margin - extents.width - 5, y_pos + extents.height/2)
            cr.show_text(time_str)
            
            # Grid line
            cr.set_source_rgba(text_color.red, text_color.green, text_color.blue, 0.1)
            cr.set_line_width(0.5)
            cr.move_to(left_margin, y_pos)
            cr.line_to(left_margin + graph_width, y_pos)
            cr.stroke()

        # Date labels
        if date_range:
            cr.set_font_size(9)
            step = max(1, len(date_range) // 8)
            for i in range(0, len(date_range), step):
                if i >= len(date_range):
                    continue
                
                try:
                    date_obj = datetime.strptime(date_range[i], "%Y-%m-%d")
                    label = date_obj.strftime("%m/%d")
                except:
                    label = date_range[i][-5:] if len(date_range[i]) >= 5 else date_range[i]
                
                x_pos = left_margin + (i * graph_width / max(len(date_range) - 1, 1))
                extents = cr.text_extents(label)
                cr.set_source_rgba(text_color.red, text_color.green, text_color.blue, text_color.alpha)
                cr.move_to(x_pos - extents.width/2, top_margin + graph_height + extents.height + 5)
                cr.show_text(label)

    def draw_no_data_indicators(self, cr, date_range, left_margin, top_margin, graph_width, graph_height, text_color):
        """Draw vertical gradient lines for dates with no data"""
        for date_idx, date in enumerate(date_range):
            if date in self.timeline_data:
                continue  # Skip dates that have data
            
            # Calculate x position
            x_pos = left_margin + 10 + (date_idx * (graph_width - 20) / max(len(date_range) - 1, 1))
            
            # Create vertical gradient from top (100% opacity) to bottom (0% opacity)
            gradient = cairo.LinearGradient(x_pos, top_margin, x_pos, top_margin + graph_height)
            
            # Use a muted color based on the text color
            base_alpha = 0.3
            gradient.add_color_stop_rgba(0, text_color.red, text_color.green, text_color.blue, base_alpha)  # Top: visible
            gradient.add_color_stop_rgba(1, text_color.red, text_color.green, text_color.blue, 0.0)        # Bottom: transparent
            
            # Draw the gradient line
            cr.set_source(gradient)
            cr.set_line_width(1.5)
            cr.move_to(x_pos, top_margin)
            cr.line_to(x_pos, top_margin + graph_height)
            cr.stroke()

    def draw_meals(self, cr, date_range, left_margin, top_margin, graph_width, graph_height):
        self.meal_circles = []
        
        # First pass: collect all circles and sort them by radius (largest first for drawing)
        circles_to_draw = []
        
        for date_idx, date in enumerate(date_range):
            if date not in self.timeline_data:
                continue
                
            # Calculate x position with padding to prevent overflow
            x_base = left_margin + 10 + (date_idx * (graph_width - 20) / max(len(date_range) - 1, 1))
            
            for meal in self.timeline_data[date]:
                try:
                    dt = datetime.strptime(meal['timestamp'], "%Y-%m-%d %H:%M:%S")
                    time_decimal = dt.hour + dt.minute / 60.0
                    # Flip the y-position calculation (00:00 at bottom)
                    y_pos = top_margin + graph_height - (time_decimal / 23) * graph_height
                    
                    # Calculate meal properties
                    kcal = meal.get('kcal', 0)
                    gram = meal.get('gram', 1)
                    radius = max(3, min(10, (kcal / 100) ** 0.7 * 5))  # Reduced max radius
                    calorie_density = kcal / gram if gram > 0 else 0
                    alpha = min(1.0, max(0.3, 0.3 + (calorie_density / 10) * 0.7))
                    
                    # Get meal category and color
                    category = self.visualizer.get_meal_category(dt.hour)
                    color = self.visualizer.meal_colors.get(category, (0.5, 0.5, 0.5))
                    
                    # Ensure the circle stays within bounds
                    x_pos = max(left_margin + radius + 5, min(x_base, left_margin + graph_width - radius - 5))
                    y_pos = max(top_margin + radius + 5, min(y_pos, top_margin + graph_height - radius - 5))
                    
                    circle_info = {
                        'x': x_pos, 'y': y_pos, 'radius': radius,
                        'date': date, 'meal': meal, 'category': category,
                        'color': color, 'alpha': alpha
                    }
                    
                    circles_to_draw.append(circle_info)
                    
                except:
                    continue
        
        # Sort circles by radius (largest first) for drawing order
        # This ensures larger circles are drawn first and smaller ones appear on top
        circles_to_draw.sort(key=lambda c: c['radius'], reverse=True)
        
        # Draw all circles
        for circle_info in circles_to_draw:
            x_pos = circle_info['x']
            y_pos = circle_info['y']
            radius = circle_info['radius']
            color = circle_info['color']
            alpha = circle_info['alpha']
            
            # Check if this specific circle is the hovered one
            is_hovered = (self.hover_meal and 
                         self.hover_meal.get('x') == x_pos and 
                         self.hover_meal.get('y') == y_pos and
                         self.hover_meal.get('radius') == radius)
            
            # Highlight if hovered
            if is_hovered:
                cr.set_source_rgba(*color, min(1.0, alpha + 0.3))
                cr.arc(x_pos, y_pos, radius + 2, 0, 2 * pi)
                cr.fill()
            
            # Main circle
            cr.set_source_rgba(*color, alpha)
            cr.arc(x_pos, y_pos, radius, 0, 2 * pi)
            cr.fill()
            
            # White outline
            cr.set_source_rgba(1, 1, 1, alpha * 0.5)
            cr.set_line_width(1)
            cr.arc(x_pos, y_pos, radius, 0, 2 * pi)
            cr.stroke()
        
        # Store circles sorted by radius (smallest first) for hover detection
        # This ensures smaller circles get priority in hover detection
        self.meal_circles = sorted(circles_to_draw, key=lambda c: c['radius'])

    def on_motion_notify(self, widget, event):
        closest_meal = None
        
        # Iterate through circles in reverse order (smallest radius first due to sorting)
        # This gives priority to smaller circles when they overlap with larger ones
        for meal_info in reversed(self.meal_circles):
            dist = ((meal_info['x'] - event.x) ** 2 + (meal_info['y'] - event.y) ** 2) ** 0.5
            if dist < meal_info['radius'] + 3:
                # If we find a smaller circle that contains the mouse, prefer it
                if closest_meal is None or meal_info['radius'] < closest_meal['radius']:
                    closest_meal = meal_info
        
        # Always update and redraw if the hovered meal changes (including None to meal or meal to None)
        if closest_meal != self.hover_meal:
            self.hover_meal = closest_meal
            self.queue_draw()
            return True
        return False
    
    def on_leave_notify(self, widget, event):
        if self.hover_meal:
            self.hover_meal = None
            self.queue_draw()
    
    def on_query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        if not self.hover_meal:
            return False
        
        meal = self.hover_meal['meal']
        date = self.hover_meal['date']
        category = self.hover_meal['category']
        
        try:
            date_str = datetime.strptime(date, "%Y-%m-%d").strftime("%B %d, %Y")
            time_str = datetime.strptime(meal['timestamp'], "%Y-%m-%d %H:%M:%S").strftime("%H:%M")
        except:
            date_str = date
            time_str = "Unknown time"
        
        calorie_density = meal.get('kcal', 0) / max(meal.get('gram', 1), 1)
        
        # Escape all text fields that might contain special characters
        food_text = self.visualizer.escape_markup(meal.get('ate', 'Unknown'))
        
        tooltip_text = (f"<b>{date_str} at {time_str}</b>\n"
                       f"Category: {category.title()}\n"
                       f"Food: {food_text}\n"
                       f"Amount: {meal.get('gram', 0):.0f}g\n"
                       f"Calories: {meal.get('kcal', 0):.0f} kcal\n"
                       f"Density: {calorie_density:.1f} kcal/g\n"
                       f"Protein: {meal.get('protein', 0):.1f}g")
        
        tooltip.set_markup(tooltip_text)
        return True

class TimelineTab(Gtk.Box):
    def __init__(self, window_width=1200, window_height=780):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.set_border_width(10)
        
        self.window_width = window_width
        self.window_height = window_height
        
        # Initialize data
        self.db_dir = self.get_db_directory()
        self.journal_data = self.load_journal_entries()
        self.timeline_data = TimelineVisualizer().process_journal_data(self.journal_data)
        
        # Build UI
        self.create_controls()
        self.create_timeline_plot()

    def get_db_directory(self):
        """Determine the correct database directory path"""
        if 'APPIMAGE' in os.environ:
            base_dir = os.path.dirname(os.environ['APPIMAGE'])
        elif getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        db_dir = os.path.join(base_dir, 'db')
        os.makedirs(db_dir, exist_ok=True)
        return db_dir

    def load_journal_entries(self):
        """Load journal entries from JSON file"""
        try:
            journal_path = os.path.join(self.db_dir, 'journal.json')
            if os.path.exists(journal_path):
                with open(journal_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('entries', []) if isinstance(data, dict) else data if isinstance(data, list) else []
        except Exception as e:
            print(f"Error loading journal data: {e}")
        return []

    def create_controls(self):
        """Create the control panel at the top right"""
        controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        controls_box.set_halign(Gtk.Align.END)
        
        # Date range selector
        self.range_combo = Gtk.ComboBoxText()
        for value, label in [("7", "7 days"), ("14", "14 days"), ("30", "30 days"), ("60", "60 days")]:
            self.range_combo.append(value, label)
        self.range_combo.set_active_id("30")
        self.range_combo.connect("changed", self.on_range_changed)
        controls_box.pack_start(self.range_combo, False, False, 0)
        
        self.pack_start(controls_box, False, False, 0)

    def create_timeline_plot(self):
        """Create or recreate the timeline visualization"""
        # Remove existing plot if it exists
        children = self.get_children()
        if len(children) > 1:
            self.remove(children[1])
        
        # Create a fixed size container to prevent scrolling
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        if not self.timeline_data:
            # Show message if no data
            label = Gtk.Label(label="No timeline data available.\nAdd journal entries with timestamps.")
            label.set_halign(Gtk.Align.CENTER)
            label.set_valign(Gtk.Align.CENTER)
            container.pack_start(label, True, True, 0)
        else:
            # Create timeline graph
            days = int(self.range_combo.get_active_id() or "30")
            timeline_graph = TimelineGraph(self.timeline_data, days)
            timeline_graph.set_size_request(self.window_width - 20, self.window_height - 150)  # Fixed size
            container.pack_start(timeline_graph, True, True, 0)
        
        self.pack_start(container, True, True, 0)
        self.show_all()

    def on_range_changed(self, combo):
        """Handle changes to the date range selection"""
        self.create_timeline_plot()

    def update_timeline(self):
        """Refresh the timeline with current data"""
        self.journal_data = self.load_journal_entries()
        self.timeline_data = TimelineVisualizer().process_journal_data(self.journal_data)
        self.create_timeline_plot()
