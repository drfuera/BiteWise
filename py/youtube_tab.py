import requests
import re
import json
import time
import os
import sys
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.1')
from gi.repository import Gtk, WebKit2, GLib, GdkPixbuf, Gdk

class YouTubeTab(Gtk.Box):
    def __init__(self, window_width, window_height):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        
        # Initialize state variables
        self.current_query = ""
        self.search_continuation = None
        self.current_results = []
        self.thumbnail_cache = {}
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.current_bookmarks_dialog = None
        self.should_cancel_search = False
        self.load_more_row = None
        self.load_more_btn = None
        self.load_more_spinner = None
        self.db_dir = self._get_db_dir()

        # Setup main UI components
        self._setup_main_ui(window_width, window_height)
        self.show_all()

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

    def _setup_main_ui(self, window_width, window_height):
        """Initialize the main UI layout"""
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.paned.set_position(int(window_width * 0.382))
        
        # Setup left and right panels
        self._setup_search_panel()
        self._setup_video_panel()
        
        self.pack_start(self.paned, True, True, 0)
        self.show_message("Base your search on available ingredients to find new recipes\n")

    def _setup_search_panel(self):
        """Configure the search results panel"""
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        
        # Search bar components
        search_box = Gtk.Box(spacing=6, margin=6)
        self.search_entry = Gtk.SearchEntry(placeholder_text="Search YouTube...")
        self.search_entry.connect("activate", self.on_search)
        
        search_btn = Gtk.Button(label="Search")
        search_btn.connect("clicked", self.on_search)
        
        bookmark_btn = Gtk.Button(label="Bookmarks")
        bookmark_btn.connect("clicked", self.show_bookmarks_dialog)
        
        search_box.pack_start(self.search_entry, True, True, 0)
        search_box.pack_start(search_btn, False, False, 0)
        search_box.pack_start(bookmark_btn, False, False, 0)
        left_box.pack_start(search_box, False, False, 0)

        # Results list setup
        self.results_scroll = Gtk.ScrolledWindow()
        self.results_list = Gtk.ListBox()
        self.results_list.connect("row-activated", self.on_row_activated)
        self.results_scroll.add(self.results_list)
        left_box.pack_start(self.results_scroll, True, True, 0)
        
        self.paned.pack1(left_box, True, True)

    def _setup_video_panel(self):
        """Configure the video player panel"""
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        self.webview = WebKit2.WebView()
        scroll = Gtk.ScrolledWindow()
        scroll.add(self.webview)
        right_box.pack_start(scroll, True, True, 0)
        
        self.paned.pack2(right_box, True, True)
        self.webview.set_background_color(Gdk.RGBA(0, 0, 0, 0))

    def _create_video_row(self, video_data, is_bookmark=False):
        """Create a standardized row for video results"""
        row = Gtk.ListBoxRow()
        row.set_size_request(-1, 90)
        row.video_id = video_data['id']
        
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        hbox.set_margin_start(6)
        hbox.set_margin_end(6)
        hbox.set_margin_top(4)
        hbox.set_margin_bottom(4)
        row.add(hbox)

        # Thumbnail image
        thumb = Gtk.Image()
        thumb.set_size_request(120, 68)
        self._load_thumbnail(thumb, video_data['id'], video_data.get('thumbnail'))
        hbox.pack_start(thumb, False, False, 0)

        # Video info container
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        info_box.set_valign(Gtk.Align.START)
        info_box.set_margin_top(5)
        hbox.pack_start(info_box, True, True, 0)

        # Video title
        title = Gtk.Label()
        title.set_markup(f'<span size="12000" weight="bold">{self._escape_text(video_data["title"])}</span>')
        title.set_xalign(0)
        title.set_line_wrap(True)
        title.set_max_width_chars(30)
        title.set_ellipsize(3)
        info_box.pack_start(title, False, False, 0)

        # Video duration
        if 'duration' in video_data:
            duration_label = Gtk.Label()
            duration_label.set_markup(f'<span size="10000" color="#bbbbbb">⏱ {video_data["duration"]}</span>')
            duration_label.set_xalign(0)
            info_box.pack_start(duration_label, False, False, 0)

        # Action buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button_box.set_halign(Gtk.Align.END)
        
        if is_bookmark:
            remove_btn = Gtk.Button(label="Remove")
            remove_btn.connect("clicked", self.on_remove_bookmark, video_data['id'])
            button_box.pack_start(remove_btn, False, False, 0)
        else:
            bookmark_btn = Gtk.Button(label="⭐")
            bookmark_btn.connect("clicked", self.on_bookmark_clicked, video_data['id'])
            button_box.pack_start(bookmark_btn, False, False, 0)
        
        info_box.pack_start(button_box, False, False, 0)
        
        return row

    def _load_thumbnail(self, image_widget, video_id, thumb_url=None):
        """Load and cache video thumbnails asynchronously"""
        def set_image(pixbuf):
            image_widget.set_from_pixbuf(pixbuf)
        
        if video_id in self.thumbnail_cache:
            GLib.idle_add(set_image, self.thumbnail_cache[video_id])
            return

        def fetch_thumbnail():
            try:
                url = thumb_url or f"https://img.youtube.com/vi/{video_id}/default.jpg"
                response = requests.get(url, stream=True, timeout=5)
                response.raise_for_status()
                
                loader = GdkPixbuf.PixbufLoader.new()
                loader.write(response.content)
                loader.close()
                
                pixbuf = loader.get_pixbuf()
                if pixbuf:
                    scaled = pixbuf.scale_simple(120, 68, GdkPixbuf.InterpType.BILINEAR)
                    self.thumbnail_cache[video_id] = scaled
                    GLib.idle_add(set_image, scaled)
            except Exception:
                GLib.idle_add(image_widget.set_from_icon_name, "image-missing", Gtk.IconSize.DIALOG)

        self.executor.submit(fetch_thumbnail)

    def on_search(self, widget):
        """Handle search requests"""
        query = self.search_entry.get_text().strip()
        if not query:
            return

        # Cancel any ongoing search
        if hasattr(self, 'search_future') and self.search_future and not self.search_future.done():
            self.should_cancel_search = True
            self.search_future.cancel()

        # Reset search state
        self.current_query = query
        self.current_results = []
        self.search_continuation = None
        self.should_cancel_search = False
        self.show_message("Searching...")

        # Remove any existing load more row
        self._remove_load_more_row()

        # Start new search
        self.search_future = self.executor.submit(self._execute_search, query)

    def _execute_search(self, query, continuation=None):
        """Perform search in background thread"""
        if self.should_cancel_search:
            return

        try:
            if continuation:
                results, new_continuation = self._fetch_continuation_results(continuation)
            else:
                results, new_continuation = self._fetch_initial_results(query)

            if not self.should_cancel_search:
                GLib.idle_add(self._display_results, results, new_continuation)

        except Exception as e:
            if not self.should_cancel_search:
                print(f"Search error: {str(e)}")
                GLib.idle_add(self.show_message, "Search error")

    def _fetch_initial_results(self, query):
        """Fetch first page of search results"""
        try:
            url = f"https://www.youtube.com/results?search_query={quote(query)}"
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Accept-Language": "en-US,en;q=0.9"
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            match = re.search(r'var ytInitialData = ({.*?});</script>', response.text)
            if match:
                return self._parse_search_results(json.loads(match.group(1)))
            
        except Exception as e:
            print(f"Search error: {str(e)}")
        
        return [], None

    def _parse_search_results(self, data):
        """Extract videos and continuation token from YouTube response"""
        videos = []
        continuation = None
        
        contents = data.get('contents', {}).get('twoColumnSearchResultsRenderer', {}).get('primaryContents', {}).get('sectionListRenderer', {}).get('contents', [])
        
        for section in contents:
            if 'itemSectionRenderer' in section:
                for item in section['itemSectionRenderer']['contents']:
                    if 'videoRenderer' in item:
                        video = item['videoRenderer']
                        try:
                            video_data = {
                                'id': video['videoId'],
                                'title': video['title']['runs'][0]['text'],
                                'duration': video.get('lengthText', {}).get('simpleText', 'N/A'),
                                'thumbnail': video['thumbnail']['thumbnails'][0]['url']
                            }
                            videos.append(video_data)
                        except KeyError:
                            continue
            
            elif 'continuationItemRenderer' in section:
                continuation = section['continuationItemRenderer']['continuationEndpoint']['continuationCommand']['token']
        
        return videos[:20], continuation

    def _fetch_continuation_results(self, continuation_token):
        """Fetch additional results using continuation token"""
        try:
            url = "https://www.youtube.com/youtubei/v1/search"
            params = {"key": "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"}
            
            payload = {
                "context": {
                    "client": {
                        "hl": "en",
                        "gl": "US",
                        "clientName": "WEB",
                        "clientVersion": "2.20210721.00.00"
                    }
                },
                "continuation": continuation_token
            }
            
            response = requests.post(url, params=params, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            videos = []
            new_continuation = None
            
            items = data.get('onResponseReceivedCommands', [{}])[0].get('appendContinuationItemsAction', {}).get('continuationItems', [])
            
            for item in items:
                if 'itemSectionRenderer' in item:
                    for content in item['itemSectionRenderer']['contents']:
                        if 'videoRenderer' in content:
                            video = content['videoRenderer']
                            try:
                                video_data = {
                                    'id': video['videoId'],
                                    'title': video['title']['runs'][0]['text'],
                                    'duration': video.get('lengthText', {}).get('simpleText', 'N/A'),
                                    'thumbnail': video['thumbnail']['thumbnails'][0]['url']
                                }
                                videos.append(video_data)
                            except KeyError:
                                continue
                
                elif 'continuationItemRenderer' in item:
                    new_continuation = item['continuationItemRenderer']['continuationEndpoint']['continuationCommand']['token']
            
            return videos, new_continuation
            
        except Exception as e:
            print(f"Continuation error: {str(e)}")
            return [], None

    def _display_results(self, results, continuation):
        """Update UI with search results"""
        if not results and not self.current_results:
            self.show_message("No results found")
            return
            
        self.search_continuation = continuation
        
        # Reset load more button state if we have results
        if results:
            self._reset_load_more_button()
        
        self.current_results.extend(results)
        
        # Clear existing results but keep any message
        for child in self.results_list.get_children():
            if not isinstance(child, Gtk.Label):
                self.results_list.remove(child)
        
        # Add new results
        for result in self.current_results:
            self.results_list.add(self._create_video_row(result))
        
        # Add or update load more button
        if continuation:
            self._add_load_more_button()
        else:
            self._remove_load_more_row()
        
        self.results_list.show_all()

    def _add_load_more_button(self):
        """Add 'Load more' button at bottom of results with spinner"""
        if self.load_more_row is None:
            self.load_more_row = Gtk.ListBoxRow()
            self.load_more_row.set_selectable(False)
            self.load_more_row.set_activatable(False)
            
            center_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            center_box.set_halign(Gtk.Align.CENTER)
            center_box.set_margin_top(10)
            center_box.set_margin_bottom(10)
            self.load_more_row.add(center_box)
            
            self.load_more_btn = Gtk.Button(label="Load more results")
            self.load_more_btn.connect("clicked", self.on_load_more)
            center_box.pack_start(self.load_more_btn, False, False, 0)
            
            self.load_more_spinner = Gtk.Spinner()
            self.load_more_btn.set_image(self.load_more_spinner)
            self.load_more_btn.set_always_show_image(True)
            self.load_more_spinner.hide()
        
        # Ensure only one load more row exists
        self._remove_load_more_row()
        self.results_list.add(self.load_more_row)

    def _remove_load_more_row(self):
        """Remove the load more row if it exists"""
        if self.load_more_row and self.load_more_row in self.results_list.get_children():
            self.results_list.remove(self.load_more_row)

    def _reset_load_more_button(self):
        """Reset the load more button to its default state"""
        if self.load_more_btn and self.load_more_spinner:
            self.load_more_btn.set_sensitive(True)
            self.load_more_btn.set_label("Load more results")
            self.load_more_spinner.hide()
            self.load_more_spinner.stop()

    def on_load_more(self, widget):
        """Handle load more button click"""
        if not self.search_continuation or (hasattr(self, 'search_future') and self.search_future and not self.search_future.done()):
            return
        
        # Show loading state
        self.load_more_btn.set_sensitive(False)
        self.load_more_btn.set_label("Loading...")
        self.load_more_spinner.show()
        self.load_more_spinner.start()
        
        # Start loading more results
        self.search_future = self.executor.submit(
            self._execute_search,
            self.current_query,
            self.search_continuation
        )

    def show_bookmarks_dialog(self, widget):
        """Display bookmarks dialog"""
        if self.current_bookmarks_dialog:
            self.current_bookmarks_dialog.destroy()

        dialog = Gtk.Dialog(
            title="Your Bookmarks",
            transient_for=self.get_toplevel(),
            modal=True,
            destroy_with_parent=True
        )
        self.current_bookmarks_dialog = dialog
        dialog.set_default_size(600, 500)
        
        # Create scrolled window for bookmarks
        scrolled = Gtk.ScrolledWindow()
        self.bookmarks_list = Gtk.ListBox()
        self.bookmarks_list.connect("row-activated", self.on_bookmark_row_activated)
        scrolled.add(self.bookmarks_list)
        dialog.get_content_area().pack_start(scrolled, True, True, 0)
        
        # Load bookmarks
        bookmarks = self._load_bookmarks()
        if not bookmarks:
            label = Gtk.Label(label="No bookmarks yet")
            label.set_margin_top(20)
            self.bookmarks_list.add(label)
        else:
            for bookmark in bookmarks:
                self.bookmarks_list.add(self._create_video_row(bookmark, is_bookmark=True))
        
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)
        dialog.show_all()
        dialog.run()
        dialog.destroy()
        self.current_bookmarks_dialog = None

    def on_bookmark_row_activated(self, listbox, row):
        """Handle bookmark selection"""
        if hasattr(row, 'video_id'):
            self.play_video(row.video_id)
            listbox.get_toplevel().response(Gtk.ResponseType.CLOSE)

    def _load_bookmarks(self):
        """Load bookmarks from JSON file"""
        bookmarks_path = os.path.join(self.db_dir, "youtube.json")
        if not os.path.exists(bookmarks_path):
            return []
        
        try:
            with open(bookmarks_path, 'r', encoding='utf-8') as f:
                bookmarks = json.load(f)
                return bookmarks if isinstance(bookmarks, list) else []
        except (json.JSONDecodeError, IOError):
            return []

    def on_remove_bookmark(self, widget, video_id):
        """Remove bookmark from storage"""
        bookmarks = [b for b in self._load_bookmarks() if b['id'] != video_id]
        
        bookmarks_path = os.path.join(self.db_dir, "youtube.json")
        with open(bookmarks_path, 'w', encoding='utf-8') as f:
            json.dump(bookmarks, f, ensure_ascii=False, indent=2)
        
        # Refresh dialog if open
        if self.current_bookmarks_dialog:
            self.refresh_bookmarks_list()

    def refresh_bookmarks_list(self):
        """Update bookmarks list in open dialog"""
        if not self.current_bookmarks_dialog:
            return
            
        # Clear existing items
        for child in self.bookmarks_list.get_children():
            self.bookmarks_list.remove(child)
        
        # Reload bookmarks
        bookmarks = self._load_bookmarks()
        if not bookmarks:
            label = Gtk.Label(label="No bookmarks yet")
            label.set_margin_top(20)
            self.bookmarks_list.add(label)
        else:
            for bookmark in bookmarks:
                self.bookmarks_list.add(self._create_video_row(bookmark, is_bookmark=True))
        
        self.bookmarks_list.show_all()

    def on_bookmark_clicked(self, widget, video_id):
        """Add current video to bookmarks"""
        video = next((v for v in self.current_results if v['id'] == video_id), None)
        if not video:
            return
        
        bookmark = {
            'id': video_id,
            'title': video['title'],
            'duration': video.get('duration', 'N/A'),
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
            'thumbnail': video.get('thumbnail', f"https://img.youtube.com/vi/{video_id}/default.jpg")
        }
        
        bookmarks = self._load_bookmarks()
        
        # Check if already bookmarked
        if any(b['id'] == video_id for b in bookmarks):
            dialog = Gtk.MessageDialog(
                transient_for=self.get_toplevel(),
                flags=0,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Already Bookmarked"
            )
            dialog.format_secondary_text("This video is already in your bookmarks.")
            dialog.run()
            dialog.destroy()
            return
        
        # Add new bookmark
        bookmarks.append(bookmark)
        
        bookmarks_path = os.path.join(self.db_dir, "youtube.json")
        with open(bookmarks_path, 'w', encoding='utf-8') as f:
            json.dump(bookmarks, f, ensure_ascii=False, indent=2)
        
        # Show confirmation
        dialog = Gtk.MessageDialog(
            transient_for=self.get_toplevel(),
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="Bookmark Added"
        )
        dialog.format_secondary_text(f"'{video['title']}' has been bookmarked.")
        dialog.run()
        dialog.destroy()

    def play_video(self, video_id):
        """Load and play selected video"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body, html {{
                    margin: 0;
                    padding: 0;
                    width: 100%;
                    height: 100%;
                    overflow: hidden;
                    background-color: #000;
                }}
                iframe {{
                    width: 100%;
                    height: 100%;
                    border: none;
                }}
            </style>
        </head>
        <body>
            <iframe src="https://www.youtube.com/embed/{video_id}?autoplay=1"
                    frameborder="0"
                    allowfullscreen>
            </iframe>
        </body>
        </html>
        """
        self.webview.load_html(html, "https://www.youtube.com/")

    def on_row_activated(self, listbox, row):
        """Handle video selection from search results"""
        if hasattr(row, 'video_id'):
            self.play_video(row.video_id)

    def show_message(self, text):
        """Display message in results area"""
        self.clear_results()
        label = Gtk.Label(label=text)
        label.set_justify(Gtk.Justification.CENTER)
        label.set_margin_top(20)
        self.results_list.add(label)
        self.results_list.show_all()

    def clear_results(self):
        """Clear all search results"""
        for child in self.results_list.get_children():
            self.results_list.remove(child)

    def _escape_text(self, text):
        """Escape special characters for Pango markup"""
        return GLib.markup_escape_text(text)
