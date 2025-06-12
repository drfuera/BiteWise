import os
import json
import sys
from datetime import datetime, timedelta
from collections import OrderedDict
from math import pi
import gi
from gi.repository import Gtk, Gdk, GObject, Pango
import cairo

gi.require_version("Gtk", "3.0")

class WeightGraph(Gtk.DrawingArea):
    def __init__(self, weights_data):
        super().__init__()
        self.weights_data = weights_data
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.connect("draw", self.on_draw)
        
        self.hover_point = None
        self.set_has_tooltip(True)
        self.connect("query-tooltip", self.on_query_tooltip)
        self.add_events(Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.connect("motion-notify-event", self.on_motion_notify)
        self.connect("leave-notify-event", self.on_leave_notify)

    def calculate_averages(self):
        if len(self.weights_data) < 2:
            return None, None, None
        
        dates = sorted(self.weights_data.keys())
        weights = [self.weights_data[date] for date in dates]
        
        # Calculate daily average
        total_days = (datetime.strptime(dates[-1], "%Y-%m-%d") - datetime.strptime(dates[0], "%Y-%m-%d")).days
        if total_days == 0:
            daily_avg = 0
        else:
            daily_avg = (weights[-1] - weights[0]) / total_days
        
        # Calculate weekly average (7 days)
        weekly_avg = daily_avg * 7
        
        # Calculate monthly average (30 days)
        monthly_avg = daily_avg * 30
        
        return daily_avg, weekly_avg, monthly_avg

    def on_draw(self, widget, cr):
        width, height = widget.get_allocated_width(), widget.get_allocated_height()
        style_context = widget.get_style_context()
        bg_color = style_context.get_background_color(Gtk.StateFlags.NORMAL)
        text_color = style_context.get_color(Gtk.StateFlags.NORMAL)
        weight_color = (0.4, 0.7, 1.0, 1.0)
        
        cr.set_source_rgba(bg_color.red, bg_color.green, bg_color.blue, bg_color.alpha)
        cr.rectangle(0, 0, width, height)
        cr.fill()
        
        if not self.weights_data:
            cr.set_source_rgba(text_color.red, text_color.green, text_color.blue, text_color.alpha)
            cr.set_font_size(14)
            text = "No weight data available."
            extents = cr.text_extents(text)
            cr.move_to(width/2 - extents.width/2, height/2 - extents.height/2)
            cr.show_text(text)
            return
        
        dates, weights = zip(*sorted(self.weights_data.items()))
        
        min_weight = max(50, min(weights) * 0.95)
        max_weight = min(150, max(weights) * 1.05)
        weight_range = max_weight - min_weight
        
        left_margin, right_margin = 60, 60
        top_margin, bottom_margin = 100, 60  # Increased top_margin from 80 to 100
        graph_width = max(width - left_margin - right_margin, 1)
        graph_height = max(height - top_margin - bottom_margin, 1)
        
        cr.set_source_rgba(text_color.red, text_color.green, text_color.blue, text_color.alpha)
        cr.set_font_size(14)
        title = "Weight development"
        cr.move_to(width/2 - cr.text_extents(title).width/2, 30)
        cr.show_text(title)
        
        # Display averages if we have enough data
        daily_avg, weekly_avg, monthly_avg = self.calculate_averages()
        if daily_avg is not None:
            avg_text = f"Avg change: {daily_avg:+.2f} kg/day, {weekly_avg:+.2f} kg/week, {monthly_avg:+.2f} kg/month"
            cr.set_font_size(10)
            extents = cr.text_extents(avg_text)
            cr.move_to(width/2 - extents.width/2, 55)  # Moved down from 50 to 55
            cr.show_text(avg_text)
        
        cr.set_source_rgba(text_color.red, text_color.green, text_color.blue, 0.5)
        cr.set_line_width(1)
        cr.move_to(left_margin, height - bottom_margin)
        cr.line_to(width - right_margin, height - bottom_margin)
        cr.stroke()
        cr.move_to(left_margin, top_margin)
        cr.line_to(left_margin, height - bottom_margin)
        cr.stroke()
        
        cr.set_source_rgba(text_color.red, text_color.green, text_color.blue, text_color.alpha)
        cr.set_font_size(10)
        num_y_ticks = 5
        for i in range(num_y_ticks + 1):
            y_pos = height - bottom_margin - (i * graph_height / num_y_ticks)
            value = min_weight + (i * weight_range / num_y_ticks)
            label = f"{value:.1f}"
            extents = cr.text_extents(label)
            cr.move_to(left_margin - extents.width - 5, y_pos + extents.height/2)
            cr.show_text(label)
            
            cr.set_source_rgba(text_color.red, text_color.green, text_color.blue, 0.2)
            cr.set_line_width(0.5)
            cr.move_to(left_margin, y_pos)
            cr.line_to(width - right_margin, y_pos)
            cr.stroke()
            cr.set_source_rgba(text_color.red, text_color.green, text_color.blue, text_color.alpha)
        
        num_dates = len(dates)
        step = max(1, num_dates // 10)
        for i in range(0, num_dates, step):
            date_str = dates[i]
            try:
                label = datetime.strptime(date_str, "%Y-%m-%d").strftime("%b %d")
            except:
                label = date_str
            
            x_pos = left_margin + (i * graph_width / max(num_dates - 1, 1))
            extents = cr.text_extents(label)
            cr.move_to(x_pos - extents.width/2, height - bottom_margin + extents.height + 5)
            cr.show_text(label)
        
        cr.set_source_rgba(*weight_color)
        cr.set_line_width(2)
        points = []
        for i, (date_str, weight) in enumerate(zip(dates, weights)):
            x_pos = left_margin + (i * graph_width / max(num_dates - 1, 1))
            y_pos = height - bottom_margin - ((weight - min_weight) / weight_range * graph_height)
            points.append((x_pos, y_pos))
            cr.line_to(x_pos, y_pos) if i else cr.move_to(x_pos, y_pos)
        cr.stroke()
        
        point_radius = 5
        if num_dates <= 100:
            cr.set_source_rgba(*weight_color)
            for x_pos, y_pos in points:
                cr.arc(x_pos, y_pos, point_radius, 0, 2 * pi)
                cr.fill()
        
        if self.hover_point is not None and self.hover_point < len(points):
            x_pos, y_pos = points[self.hover_point]
            cr.set_source_rgba(weight_color[0], weight_color[1], weight_color[2], 0.8)
            cr.arc(x_pos, y_pos, point_radius + 2, 0, 2 * pi)
            cr.fill()
        
        self.graph_points, self.graph_dates, self.graph_weights = points, dates, weights
        
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(10)
        label = "Weight"
        extents = cr.text_extents(label)
        total_width = 12 + 5 + extents.width
        
        legend_x, legend_y = (width - total_width) / 2, 69  # Increased from 49 to 69
        cr.set_source_rgba(0.2, 0.2, 0.2, 0.8)
        cr.rectangle(legend_x - 5, legend_y - 5, total_width + 10, extents.height + 10)
        cr.fill()
        
        cr.set_source_rgba(0.8, 0.8, 0.8, 0.8)
        cr.set_line_width(1)
        cr.rectangle(legend_x - 5, legend_y - 5, total_width + 10, extents.height + 10)
        cr.stroke()
        
        cr.set_source_rgba(*weight_color)
        cr.rectangle(legend_x, legend_y + 1, 12, 10)
        cr.fill()
        cr.set_source_rgba(1, 1, 1, 1)
        cr.move_to(legend_x + 17, legend_y + extents.height + 1)
        cr.show_text("Weight")

    def on_motion_notify(self, widget, event):
        if not hasattr(self, 'graph_points'):
            return False
        
        closest_point, min_dist = None, float('inf')
        for i, (x, y) in enumerate(self.graph_points):
            dist = (x - event.x)**2 + (y - event.y)**2
            if dist < min_dist and dist < 400:
                min_dist = dist
                closest_point = i
        
        if closest_point != self.hover_point:
            self.hover_point = closest_point
            self.queue_draw()
            return closest_point is not None
        
        return False
    
    def on_leave_notify(self, widget, event):
        if self.hover_point is not None:
            self.hover_point = None
            self.queue_draw()
    
    def on_query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        if not hasattr(self, 'graph_points') or self.hover_point is None:
            return False
        
        date = self.graph_dates[self.hover_point]
        weight = self.graph_weights[self.hover_point]
        try:
            date_str = datetime.strptime(date, "%Y-%m-%d").strftime("%B %d, %Y")
        except:
            date_str = date
        
        tooltip.set_markup(f"<b>{date_str}</b>\nWeight: {weight:.1f} kg")
        return True

class WeightStatsTab(Gtk.Box):
    def __init__(self, window_width, window_height):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_border_width(10)
        self.db_dir = self._get_db_dir()
        self.journal_data = self._load_journal_data()
        self.daily_weights = self._process_weight_data()
        self.create_weight_plot()

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
            if os.path.exists(journal_path):
                with open(journal_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('entries', []) if isinstance(data, dict) else data if isinstance(data, list) else []
        except Exception as e:
            print(f"Problem loading journal data: {e}")
        return []

    def _process_weight_data(self):
        return OrderedDict((e['date'], e['weight']) for e in self.journal_data 
                if isinstance(e, dict) and 'date' in e and 'weight' in e 
                and isinstance(e['weight'], (int, float)) and e['weight'] > 0)

    def create_weight_plot(self):
        for child in self.get_children():
            self.remove(child)
        
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        scrolled.add(box)
        
        if not self.daily_weights:
            label = Gtk.Label(label="No weight data available.")
            label.set_halign(Gtk.Align.CENTER)
            label.set_valign(Gtk.Align.CENTER)
            box.pack_start(label, True, True, 0)
        else:
            box.pack_start(WeightGraph(self.daily_weights), True, True, 0)
        
        self.pack_start(scrolled, True, True, 0)
        self.show_all()

    def update_plot(self):
        self.journal_data = self._load_journal_data()
        self.daily_weights = self._process_weight_data()
        self.create_weight_plot()
