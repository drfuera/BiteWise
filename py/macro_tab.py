import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk
import cairo
import json
import os
import math
from collections import defaultdict
import operator

class PieChart(Gtk.DrawingArea):
    def __init__(self, title, data):
        super().__init__()
        self.title = title
        self.data = {k: v for k, v in data.items() if v != 0}  # Filter zero values early
        self.set_size_request(350, 350)
        self.connect("draw", self.on_draw)
        self.hover_slice = None
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
        
        cr.set_source_rgba(*bg_color)
        cr.rectangle(0, 0, width, height)
        cr.fill()
        
        if not self.data:
            self._draw_no_data(cr, width, height, text_color)
            return
        
        total = sum(self.data.values())
        if total == 0:
            return
            
        colors = [
            (0.258, 0.521, 0.956, 1.0), (0.941, 0.298, 0.235, 1.0),
            (0.431, 0.737, 0.298, 1.0), (0.988, 0.686, 0.243, 1.0),
            (0.647, 0.317, 0.941, 1.0), (0.274, 0.741, 0.764, 1.0),
            (0.972, 0.792, 0.196, 1.0), (0.941, 0.501, 0.501, 1.0),
            (0.737, 0.741, 0.133, 1.0), (0.176, 0.502, 0.725, 1.0)
        ]
        
        radius = min(width, height) * 0.3
        center_x, center_y = width / 2, height / 2 - 10
        current_angle = -math.pi/2
        self.slices = []
        
        for i, (category, value) in enumerate(self.data.items()):
            angle = 2 * math.pi * value / total
            self.slices.append({
                'category': category,
                'value': value,
                'percentage': value / total * 100,
                'start_angle': current_angle,
                'end_angle': current_angle + angle,
                'color': colors[i % len(colors)]
            })
            
            if self.hover_slice != i:
                cr.set_source_rgba(*colors[i % len(colors)])
                cr.move_to(center_x, center_y)
                cr.arc(center_x, center_y, radius, current_angle, current_angle + angle)
                cr.line_to(center_x, center_y)
                cr.fill()
            
            current_angle += angle
        
        if self.hover_slice is not None:
            self._draw_hover_slice(cr, center_x, center_y, radius)
        self._draw_slice_borders(cr, center_x, center_y, radius)
        self._draw_title(cr, width, text_color)
        self._draw_legend(cr, width, height, text_color)
    
    def _draw_no_data(self, cr, width, height, text_color):
        cr.set_source_rgba(*text_color)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(14)
        text = "No data available"
        extents = cr.text_extents(text)
        cr.move_to(width/2 - extents.width/2, height/2 - extents.height/2)
        cr.show_text(text)
    
    def _draw_hover_slice(self, cr, center_x, center_y, radius):
        slice_info = self.slices[self.hover_slice]
        r, g, b, a = slice_info['color']
        cr.set_source_rgba(min(r * 1.3, 1.0), min(g * 1.3, 1.0), min(b * 1.3, 1.0), a)
        cr.move_to(center_x, center_y)
        cr.arc(center_x, center_y, radius * 1.05, slice_info['start_angle'], slice_info['end_angle'])
        cr.line_to(center_x, center_y)
        cr.fill()
        
        cr.set_source_rgba(1, 1, 1, 0.8)
        cr.set_line_width(2)
        cr.arc(center_x, center_y, radius * 1.05, slice_info['start_angle'], slice_info['end_angle'])
        cr.stroke()
    
    def _draw_slice_borders(self, cr, center_x, center_y, radius):
        cr.set_source_rgba(1, 1, 1, 0.5)
        cr.set_line_width(0.5)
        for slice_info in self.slices:
            cr.move_to(center_x, center_y)
            cr.line_to(center_x + radius * math.cos(slice_info['start_angle']), 
                      center_y + radius * math.sin(slice_info['start_angle']))
            cr.stroke()
    
    def _draw_title(self, cr, width, text_color):
        cr.set_source_rgba(*text_color)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(14)
        extents = cr.text_extents(self.title)
        cr.move_to(width/2 - extents.width/2, 30)
        cr.show_text(self.title)
    
    def _draw_legend(self, cr, width, height, text_color):
        cr.set_font_size(10)
        legend_x, legend_y = 20, height - 50 - len(self.data) * 20
        text_items = []
        
        for i, (category, _) in enumerate(self.data.items()):
            text = f"{category[:20]}"
            extents = cr.text_extents(text)
            text_items.append((text, extents.width))
        
        max_text_width = max(w for _, w in text_items) if text_items else 0
        max_percentage_width = max(cr.text_extents(f"{s['percentage']:.1f}%").width 
                             for s in self.slices) if self.slices else 0
        
        legend_padding, swatch_size, text_spacing, item_spacing = 12, 14, 5, 4
        legend_width = swatch_size + text_spacing * 2 + max_text_width + max_percentage_width + legend_padding * 2
        legend_height = len(text_items) * (swatch_size + item_spacing) + legend_padding * 2
        
        cr.set_source_rgba(0.1, 0.1, 0.1, 0.7)
        cr.rectangle(legend_x, legend_y, legend_width, legend_height)
        cr.fill()
        
        cr.set_source_rgba(1, 1, 1, 0.3)
        cr.set_line_width(1)
        cr.rectangle(legend_x, legend_y, legend_width, legend_height)
        cr.stroke()
        
        item_y = legend_y + legend_padding
        for i, (text, _) in enumerate(text_items):
            cr.set_source_rgba(*self.slices[i]['color'])
            cr.rectangle(legend_x + legend_padding, item_y, swatch_size, swatch_size)
            cr.fill()
            
            cr.set_source_rgba(1, 1, 1, 0.8)
            cr.set_line_width(0.7)
            cr.rectangle(legend_x + legend_padding, item_y, swatch_size, swatch_size)
            cr.stroke()
            
            cr.set_source_rgba(1, 1, 1, 0.95)
            cr.move_to(legend_x + legend_padding + swatch_size + text_spacing, item_y + swatch_size - 2)
            cr.show_text(text)
            
            cr.move_to(legend_x + legend_width - legend_padding - max_percentage_width, item_y + swatch_size - 2)
            cr.show_text(f"{self.slices[i]['percentage']:.1f}%")
            
            item_y += swatch_size + item_spacing

    def on_motion_notify(self, widget, event):
        if not hasattr(self, 'slices'):
            return False
            
        width, height = widget.get_allocated_width(), widget.get_allocated_height()
        radius = min(width, height) * 0.3
        center_x, center_y = width / 2, height / 2 - 10
        
        dx, dy = event.x - center_x, event.y - center_y
        distance = (dx**2 + dy**2)**0.5
        
        if distance > radius * 1.05:
            if self.hover_slice is not None:
                self.hover_slice = None
                self.queue_draw()
            return False
            
        angle = math.atan2(dy, dx) % (2 * math.pi)
        new_hover = None
        
        for i, slice_info in enumerate(self.slices):
            start = slice_info['start_angle'] % (2 * math.pi)
            end = slice_info['end_angle'] % (2 * math.pi)
            
            if (start > end and (angle >= start or angle < end)) or (start <= angle < end):
                new_hover = i
                break
        
        if new_hover != self.hover_slice:
            self.hover_slice = new_hover
            self.queue_draw()
            return True
        return False
    
    def on_leave_notify(self, widget, event):
        if self.hover_slice is not None:
            self.hover_slice = None
            self.queue_draw()
    
    def on_query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        if not hasattr(self, 'slices') or self.hover_slice is None:
            return False
        
        slice_info = self.slices[self.hover_slice]
        tooltip.set_markup(f"<b>{slice_info['category']}</b>\nAmount: {slice_info['value']:.1f}\nPercentage: {slice_info['percentage']:.1f}%")
        return True

class MacroBreakdownTab(Gtk.Box):
    def __init__(self, window_width, window_height):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.set_border_width(10)
        self.journal_data = self._load_journal_data()
        self._create_ui()

    def _load_journal_data(self):
        try:
            journal_path = os.path.join(os.path.dirname(__file__), '../db/journal.json')
            with open(journal_path, 'r', encoding='utf-8') as f:
                return json.load(f).get('entries', [])
        except Exception:
            return []

    def _process_data(self, key):
        totals = defaultdict(float)
        for entry in self.journal_data:
            totals[entry.get('ate', 'Unknown')] += entry.get(key, 0)
        return dict(sorted(totals.items(), key=operator.itemgetter(1), reverse=True)[:10])

    def _create_ui(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        scrolled.add(main_box)
        
        # Create rows with charts
        metrics = [
            ('gram', 'Top Foods by Weight (g)'),
            ('kcal', 'Top Foods by Calories'),
            ('carbs', 'Top Foods by Carbohydrates (g)'),
            ('fat', 'Top Foods by Fat (g)'),
            ('protein', 'Top Foods by Protein (g)'),
            ('fiber', 'Top Foods by Fiber (g)')
        ]
        
        for i in range(0, len(metrics), 3):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            row.set_homogeneous(True)
            for metric, title in metrics[i:i+3]:
                row.pack_start(PieChart(title, self._process_data(metric)), True, True, 0)
            main_box.pack_start(row, False, False, 0)
        
        self.pack_start(scrolled, True, True, 0)

    def update_charts(self):
        """Reload journal data and recreate all charts"""
        self.journal_data = self._load_journal_data()
        
        # Remove all existing widgets
        for child in self.get_children():
            self.remove(child)
            
        # Recreate the UI with updated data
        self._create_ui()
        self.show_all()
