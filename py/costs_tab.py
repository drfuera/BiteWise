import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GObject
import cairo
import json
import os
import sys
from datetime import datetime
from collections import OrderedDict
import statistics
from math import pi

class CostsGraph(Gtk.DrawingArea):
    def __init__(self, costs_data, journal_data):
        super().__init__()
        self.costs_data = costs_data
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.connect("draw", self.on_draw)
        self.set_has_tooltip(True)
        self.connect("query-tooltip", self.on_query_tooltip)
        self.add_events(Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.connect("motion-notify-event", self.on_motion_notify)
        self.connect("leave-notify-event", self.on_leave_notify)
        self.hover_point = None

    def on_draw(self, widget, cr):
        width, height = widget.get_allocated_width(), widget.get_allocated_height()
        style_context = widget.get_style_context()
        bg_color = style_context.get_background_color(Gtk.StateFlags.NORMAL)
        text_color = style_context.get_color(Gtk.StateFlags.NORMAL)
        
        cr.set_source_rgba(bg_color.red, bg_color.green, bg_color.blue, bg_color.alpha)
        cr.rectangle(0, 0, width, height)
        cr.fill()
        
        if not self.costs_data:
            self._draw_no_data(cr, width, height, text_color)
            return
        
        dates = sorted(self.costs_data.keys())
        daily_costs = [self.costs_data[d] for d in dates]
        window_size = 7
        moving_avg = [
            sum(daily_costs[max(0,i-window_size//2):min(len(daily_costs),i+window_size//2+1)])/ 
            len(daily_costs[max(0,i-window_size//2):min(len(daily_costs),i+window_size//2+1)])
            for i in range(len(daily_costs))
        ]
        
        left_margin, right_margin = 60, 60
        top_margin, bottom_margin = 80, 60
        graph_width = max(width - left_margin - right_margin, 1)
        graph_height = max(height - top_margin - bottom_margin, 1)
        max_cost = max(daily_costs) * 1.1
        
        cr.set_source_rgba(*self._get_rgba(text_color))
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(14)
        self._draw_centered_text(cr, "Daily Food Costs Analysis", width/2, 30)
        
        self._draw_axes_and_grid(cr, width, height, left_margin, right_margin, 
                               top_margin, bottom_margin, graph_height, max_cost, text_color)
        
        self._draw_x_labels(cr, width, height, left_margin, bottom_margin, 
                          graph_width, dates, text_color)
        
        self._draw_bars_and_average(cr, width, height, left_margin, bottom_margin,
                                  graph_width, graph_height, max_cost, dates, 
                                  daily_costs, moving_avg)
        
        self.graph_dates, self.graph_costs, self.graph_avg = dates, daily_costs, moving_avg

    def _draw_no_data(self, cr, width, height, text_color):
        cr.set_source_rgba(*self._get_rgba(text_color))
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(14)
        self._draw_centered_text(cr, "No cost data available", width/2, height/2)

    def _draw_axes_and_grid(self, cr, width, height, left_margin, right_margin,
                          top_margin, bottom_margin, graph_height, max_value, text_color):
        cr.set_source_rgba(*self._get_rgba(text_color, 0.5))
        cr.set_line_width(1)
        cr.move_to(left_margin, height - bottom_margin)
        cr.line_to(width - right_margin, height - bottom_margin)
        cr.stroke()
        cr.move_to(left_margin, top_margin)
        cr.line_to(left_margin, height - bottom_margin)
        cr.stroke()
        
        cr.set_source_rgba(*self._get_rgba(text_color))
        cr.set_font_size(10)
        num_ticks = 5
        for i in range(num_ticks + 1):
            y_pos = height - bottom_margin - (i * graph_height / num_ticks)
            value = i * max_value / num_ticks
            label = f"{value:.0f}"
            extents = cr.text_extents(label)
            cr.move_to(left_margin - extents.width - 5, y_pos + extents.height/2)
            cr.show_text(label)
            
            cr.set_source_rgba(*self._get_rgba(text_color, 0.2))
            cr.set_line_width(0.5)
            cr.move_to(left_margin, y_pos)
            cr.line_to(width - right_margin, y_pos)
            cr.stroke()
            cr.set_source_rgba(*self._get_rgba(text_color))

    def _draw_x_labels(self, cr, width, height, left_margin, bottom_margin, 
                     graph_width, dates, text_color):
        cr.set_font_size(10)
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

    def _draw_bars_and_average(self, cr, width, height, left_margin, bottom_margin,
                             graph_width, graph_height, max_value, dates, 
                             daily_costs, moving_avg):
        num_dates = len(dates)
        bar_width = min(30, graph_width / num_dates) if num_dates > 1 else 40
        bar_spacing = (graph_width - (num_dates * bar_width)) / max(num_dates - 1, 1)
        
        self.bar_rects = []
        for i, cost in enumerate(daily_costs):
            x_pos = left_margin + (i * (bar_width + bar_spacing)) + (bar_width / 2) if num_dates > 1 else left_margin + graph_width / 2
            bar_height = (cost / max_value) * graph_height
            rect = (x_pos - bar_width/2, height - bottom_margin - bar_height, bar_width, bar_height)
            self.bar_rects.append(rect)
            
            is_hovered = (hasattr(self, 'hover_point') and self.hover_point is not None and self.hover_point == i)
            cr.set_source_rgba(0.2, 0.8, 0.4, 1.0 if not is_hovered else 0.8)
            cr.rectangle(*rect)
            cr.fill()
            
            if is_hovered:
                cr.set_source_rgba(1, 1, 1, 0.8)
                cr.set_line_width(1.5)
                cr.rectangle(*rect)
                cr.stroke()
        
        self.avg_points = []
        cr.set_source_rgba(1.0, 0.5, 0.0, 1.0)
        cr.set_line_width(2)
        
        for i, avg in enumerate(moving_avg):
            x_pos = left_margin + (i * graph_width / max(num_dates - 1, 1))
            y_pos = height - bottom_margin - ((avg / max_value) * graph_height)
            self.avg_points.append((x_pos, y_pos))
            cr.line_to(x_pos, y_pos) if i else cr.move_to(x_pos, y_pos)
        
        cr.stroke()
        
        point_radius = 3
        for i, (x_pos, y_pos) in enumerate(self.avg_points):
            is_hovered = (hasattr(self, 'hover_point') and self.hover_point is not None and self.hover_point == i)
            
            cr.set_source_rgba(1.0, 0.5, 0.0, 1.0)
            cr.arc(x_pos, y_pos, point_radius + (2 if is_hovered else 0), 0, 2 * pi)
            cr.fill()
            
            if is_hovered:
                cr.set_source_rgba(1, 1, 1, 0.8)
                cr.set_line_width(1.5)
                cr.arc(x_pos, y_pos, point_radius + 2, 0, 2 * pi)
                cr.stroke()

    def _get_rgba(self, color, alpha=None):
        return (color.red, color.green, color.blue, alpha if alpha is not None else color.alpha)

    def _draw_centered_text(self, cr, text, x, y):
        extents = cr.text_extents(text)
        cr.move_to(x - extents.width/2, y - extents.height/2)
        cr.show_text(text)

    def on_motion_notify(self, widget, event):
        if not hasattr(self, 'bar_rects') or not hasattr(self, 'avg_points'):
            return False
        
        for i, (x, y, w, h) in enumerate(self.bar_rects):
            if (x <= event.x <= x + w and y <= event.y <= y + h):
                if i != self.hover_point:
                    self.hover_point = i
                    self.queue_draw()
                return True
        
        min_dist = 10
        for i, (x_pos, y_pos) in enumerate(self.avg_points):
            if ((x_pos - event.x) ** 2 + (y_pos - event.y) ** 2) ** 0.5 < min_dist:
                if i != self.hover_point:
                    self.hover_point = i
                    self.queue_draw()
                return True
        
        if self.hover_point is not None:
            self.hover_point = None
            self.queue_draw()
        return False
    
    def on_leave_notify(self, widget, event):
        if hasattr(self, 'hover_point') and self.hover_point is not None:
            self.hover_point = None
            self.queue_draw()
    
    def on_query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        if not hasattr(self, 'graph_dates') or not hasattr(self, 'hover_point') or self.hover_point is None:
            return False
        
        date = self.graph_dates[self.hover_point]
        cost = self.graph_costs[self.hover_point]
        avg = self.graph_avg[self.hover_point]
        
        try:
            date_str = datetime.strptime(date, "%Y-%m-%d").strftime("%B %d, %Y")
        except:
            date_str = date
        
        tooltip.set_markup(f"<b>{date_str}</b>\nDaily Cost: {cost:.2f}\n7-day Avg: {avg:.2f}")
        return True

class CostsTab(Gtk.Box):
    def __init__(self, window_width, window_height):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_border_width(10)
        self.db_dir = self._get_db_dir()
        self.journal_data = self._load_journal_data()
        self.daily_costs = self._process_cost_data()
        self.create_cost_plots()

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
                    return data.get('entries', []) if isinstance(data, dict) else data
        except Exception as e:
            print(f"Error loading journal data: {e}")
        return []

    def _process_cost_data(self):
        daily_costs = OrderedDict()
        for entry in self.journal_data:
            if isinstance(entry, dict) and 'date' in entry and 'cost' in entry:
                date = entry['date']
                daily_costs[date] = daily_costs.get(date, 0.0) + entry.get('cost', 0)
        return daily_costs

    def create_cost_plots(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        scrolled.add(box)
        
        if not self.daily_costs:
            box.pack_start(Gtk.Label(label="No cost data available"), True, True, 0)
        else:
            box.pack_start(CostsGraph(self.daily_costs, self.journal_data), True, True, 0)
            box.pack_start(self._create_summary_stats(), False, False, 0)
        
        self.pack_start(scrolled, True, True, 0)

    def _create_summary_stats(self):
        stats_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        stats_box.set_homogeneous(True)
        stats_box.set_margin_top(-30)
        stats_box.set_margin_bottom(10)
        
        costs = list(self.daily_costs.values())
        stats = [
            ("Total Cost", f"{sum(costs):.2f}"),
            ("Avg Daily", f"{statistics.mean(costs):.2f}" if costs else "0.00"),
            ("Max Daily", f"{max(costs):.2f}" if costs else "0.00"),
            ("Min Daily", f"{min(costs):.2f}" if costs else "0.00")
        ]
        
        for label, value in stats:
            stat_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            stat_box.pack_start(Gtk.Label(label=label, halign=Gtk.Align.CENTER), False, False, 0)
            
            value_label = Gtk.Label(label=value, halign=Gtk.Align.CENTER)
            value_label.override_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0.4, 0.7, 1.0, 1.0))
            stat_box.pack_start(value_label, False, False, 0)
            
            stats_box.pack_start(stat_box, True, True, 0)
        
        return stats_box
