#!/usr/bin/env python3

"""
Version 3 of a GUI application to show LWATV (Tkinter + GStreamer 1.0).
"""

import os
import sys
import glob
import math
import time
import queue
import random
import argparse
import threading
from urllib.request import urlopen
from datetime import datetime, timezone
from PIL import Image as PImage
from PIL import ImageTk
from io import BytesIO

import tkinter as tk
import tkinter.font as tkfont

if sys.platform.startswith('linux'):
    import ctypes
    try:
        x11 = ctypes.cdll.LoadLibrary('libX11.so')
        x11.XInitThreads()
    except:
        pass

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import Gst, GLib
from gi.repository import GstVideo

Gst.init(None)

# Pillow resampling filter (constant moved to Image.Resampling in Pillow 9.1+)
try:
    RESAMPLE = PImage.Resampling.LANCZOS
except AttributeError:
    RESAMPLE = PImage.LANCZOS


class MoviePlayer(tk.Label):
    """
    tk.Label object to deal with playing the old movies.

    Two rendering strategies are used depending on the windowing system:

      * X11 (Linux, incl. the Raspberry Pi): the video sink renders directly
        into this widget's native window - efficient, hardware-friendly.
      * everything else (macOS/Aqua): winfo_id() is not an X11 window, so
        decoded RGB frames are pulled from an appsink and painted into the
        Label as images.
    """

    def __init__(self, parent, moviePath, label, verbose=False):
        super().__init__(parent, bg='black', bd=0, highlightthickness=0)

        self.moviePath = moviePath
        self.label = label
        self.verbose = verbose
        self._frame = None
        self.window_id = None
        self._embed = (self.tk.call('tk', 'windowingsystem') == 'x11')

        self.pipeline = Gst.Pipeline()
        self.player = Gst.ElementFactory.make("playbin", None)

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message::eos', self.on_eos_message)
        bus.connect('message::error', self.on_error_message)

        if self._embed:
            # Hand the video sink this widget's X window once it is mapped.  The
            # sync-message handler runs on the GStreamer streaming thread and
            # must not touch Tk, so the id is read on the Tk thread and cached.
            bus.enable_sync_message_emission()
            bus.connect('sync-message::element', self.on_sync_message)
            self.bind('<Map>', self._on_map)
            # playbin picks a sensible sink by default, but allow it to be
            # overridden (e.g. LWATV_VIDEO_SINK=ximagesink) for platforms where
            # the default does not embed via GstVideoOverlay.
            sinkName = os.environ.get('LWATV_VIDEO_SINK', None)
            if sinkName:
                vs = Gst.ElementFactory.make(sinkName, None)
                if vs is not None:
                    self.player.set_property("video-sink", vs)
                elif self.verbose:
                    print(f"Could not create video sink '{sinkName}'; using default")
        else:
            # Grab decoded video as raw RGB frames instead of a native window.
            self.appsink = Gst.ElementFactory.make("appsink", None)
            self.appsink.set_property("caps", Gst.Caps.from_string("video/x-raw,format=RGB"))
            self.appsink.set_property("max-buffers", 1)
            self.appsink.set_property("drop", True)
            self.player.set_property("video-sink", self.appsink)

        self.pipeline.add(self.player)

        # Tkinter has no GLib main loop of its own, so pump the default GLib
        # context from the Tk event loop to keep the bus signals (eos/error)
        # flowing.
        self.after(50, self._pump_gst)
        if not self._embed:
            self.after(33, self._render_frames)

    def _pump_gst(self):
        ctx = GLib.MainContext.default()
        while ctx.pending():
            ctx.iteration(False)
        self.after(50, self._pump_gst)

    def _on_map(self, event=None):
        # Cache the native window id now that the frame exists on the display
        self.window_id = self.winfo_id()

    def on_sync_message(self, bus, message):
        if message.get_structure().get_name() == 'prepare-window-handle':
            message.src.set_property('force-aspect-ratio', True)
            if self.window_id is not None:
                message.src.set_window_handle(self.window_id)

    def _render_frames(self):
        try:
            sample = self.appsink.emit('try-pull-sample', 0)
        except Exception:
            sample = None
        if sample is not None:
            self._show_sample(sample)
        self.after(33, self._render_frames)

    def _show_sample(self, sample):
        caps = sample.get_caps()
        st = caps.get_structure(0)
        okw, w = st.get_int('width')
        okh, h = st.get_int('height')
        if not (okw and okh):
            return

        buf = sample.get_buffer()
        ok, minfo = buf.map(Gst.MapFlags.READ)
        if not ok:
            return
        try:
            expected = w*h*3
            if minfo.size < expected:
                return
            image = PImage.frombytes('RGB', (w, h), bytes(minfo.data[:expected]))
        finally:
            buf.unmap(minfo)

        # Scale to fit the panel while preserving the aspect ratio
        ww, hh = self.winfo_width(), self.winfo_height()
        if ww > 1 and hh > 1:
            s = min(ww/float(w), hh/float(h))
            image = image.resize((max(1, int(round(w*s))), max(1, int(round(h*s)))),
                                 RESAMPLE)

        photo = ImageTk.PhotoImage(image)
        self.config(image=photo)
        self._frame = photo

    def on_eos_message(self, bus, message):
        if self.verbose:
            print("Finished movie")
        self.pipeline.set_state(Gst.State.NULL)

        self.after(0, self.advance)

    def on_error_message(self, bus, message):
        err, debug = message.parse_error()
        print(f"Error {err}: {debug}")

        self.pipeline.set_state(Gst.State.NULL)
        self.after(0, self.advance)

    def get_movie(self):
        movies = glob.glob(os.path.join(self.moviePath, '*.mov'))
        movies.sort()
        movie = random.choice(movies)

        if self.verbose:
            print(f"Next movie is {movie}")
        return movie

    def advance(self):
        # When embedding, do not start a movie until the frame is mapped and its
        # window handle is known, or the video sink gets a bad/undefined window.
        if self._embed and self.window_id is None:
            self.after(100, self.advance)
            return

        isPlaying = False
        for state in self.pipeline.get_state(0):
            if type(state) != type(Gst.State.PLAYING):
                continue
            if state == Gst.State.PLAYING:
                isPlaying = True
                break

        if not isPlaying:
            movie = self.get_movie()
            movieBase = os.path.basename(movie)
            mjd = int(movieBase.split('.', 1)[0])
            jd = mjd + 2400000.5
            t = (jd - 2440587.5)*86400.0
            dt = datetime.fromtimestamp(t, tz=timezone.utc)
            self.label.config(text=f"Movie for {dt.strftime('%B %d, %Y')}")

            self.pipeline.set_state(Gst.State.NULL)
            self.player.set_property('uri', f"file://{movie}")
            self.pipeline.set_state(Gst.State.PLAYING)

    def stop(self):
        self.pipeline.set_state(Gst.State.NULL)


class LWATV(tk.Tk):
    def __init__(self, args, title="LWATV GUI", config=None):
        super().__init__()
        self.title(title)
        self.geometry("1310x840")
        self.configure(bg='black')

        # Configuration
        self.args = args
        self.config = config if config is not None else {}

        # Paths
        basePath = os.path.dirname(os.path.abspath(__file__))
        self.infoPath = os.path.join(basePath, 'info')
        self.imagePath = os.path.join(basePath, 'images')
        self.moviePath = os.path.join(basePath, 'movies')

        # Build the UI
        self.init_ui()
        self.init_events()
        if not self.args.disable_maximize:
            try:
                self.wm_attributes('-zoomed', True)
            except tk.TclError:
                self.update_idletasks()
                sw = self.winfo_screenwidth()
                sh = self.winfo_screenheight()
                self.geometry(f"{sw}x{sh}+0+0")

        # Update
        self.init_images()
        self.update_text_size()

    def _panel(self, **gridopts):
        # A frame whose size is dictated solely by its grid cell, never by the
        # content packed inside it.  This stops images/movies/text from
        # inflating their columns and skewing the overall proportions.
        frame = tk.Frame(self.container, bg='black', width=1, height=1)
        frame.grid(**gridopts)
        frame.grid_propagate(False)
        frame.pack_propagate(False)
        return frame

    def init_ui(self):
        container = tk.Frame(self, bg='black')
        container.pack(fill='both', expand=True)
        self.container = container

        ih = 6
        iw = 6
        tw = 2

        # Fonts (copies so we can resize them without touching the shared
        # named fonts)
        base = tkfont.nametofont('TkDefaultFont')
        bsize = base.cget('size')
        labelFont = tkfont.Font(font=base)
        labelFont.configure(size=(bsize + 2) if bsize > 0 else (bsize - 2))
        self.descFont = tkfont.Font(font=base)

        # Latest LWATV Image
        ## Label
        self.latestText = tk.Label(container, text="Latest LWATV Image",
                                   fg='white', bg='black', font=labelFont)
        self.latestText.grid(row=0, column=0, columnspan=iw, padx=4, pady=4)
        ## Image
        latestFrame = self._panel(row=1, column=0, rowspan=ih//2, columnspan=iw,
                                  sticky='nsew', padx=4, pady=(0, 4))
        self.latestImage = tk.Label(latestFrame, bg='black', bd=0, highlightthickness=0)
        self.latestImage.pack(fill='both', expand=True)

        # LWA1/LWA-SV Station Image
        if not self.args.disable_movie:
            siw = iw//2
        else:
            siw = iw
        ## Label
        if self.args.lwatv4:
            stationLabel = "The LWA-NA Site Located by the VLA"
        elif self.args.lwatv2:
            stationLabel = "The LWA-SV Site Located on the Sevilleta NWR"
        else:
            stationLabel = "The LWA1 Site Located by the VLA"
        stationText = tk.Label(container, text=stationLabel,
                               fg='white', bg='black', font=labelFont)
        stationText.grid(row=2+ih, column=0, columnspan=siw, padx=4, pady=4)
        ## Image
        stationFrame = self._panel(row=2+ih//2, column=0, rowspan=ih//2, columnspan=siw,
                                   sticky='nsew', padx=4)
        self.stationImage = tk.Label(stationFrame, bg='black', bd=0, highlightthickness=0)
        self.stationImage.pack(fill='both', expand=True)

        if not self.args.disable_movie:
            # Previously Recorded Movies
            ## Label
            self.movieText = tk.Label(container, text="Previous Movies",
                                      fg='white', bg='black', font=labelFont)
            self.movieText.grid(row=2+ih, column=iw//2, columnspan=iw//2, padx=4, pady=4)
            ## Movie
            movieFrame = self._panel(row=2+ih//2, column=iw//2, rowspan=ih//2,
                                     columnspan=iw//2, sticky='nsew', padx=4)
            self.previousMovie = MoviePlayer(movieFrame, self.moviePath,
                                             self.movieText, self.args.verbose)
            self.previousMovie.pack(fill='both', expand=True)

        # Image Information
        ## Label
        descriptionLabel = tk.Label(container, text="Image Description",
                                    fg='white', bg='black', font=labelFont)
        descriptionLabel.grid(row=0, column=iw, columnspan=tw, padx=4, pady=4)
        ## Content
        descFrame = self._panel(row=1, column=iw, rowspan=ih, columnspan=tw,
                                sticky='nsew', padx=10, pady=10)
        self.descriptionText = tk.Text(descFrame, wrap='word', fg='white', bg='black',
                                       bd=0, highlightthickness=1,
                                       highlightbackground='gray60', highlightcolor='gray60',
                                       font=self.descFont, insertbackground='white',
                                       padx=6, pady=6, width=1, height=1)
        self.descriptionText.insert('1.0', "Image description here.")
        self.descriptionText.config(state='disabled')
        self.descriptionText.pack(fill='both', expand=True)
        ## Copyright Label
        copyrightLabel = tk.Label(container, text="Copyright (c) 2026 The LWA Consortium",
                                  fg='white', bg='black')
        copyrightLabel.grid(row=2+ih, column=iw, columnspan=tw, padx=4, pady=4)

        # Make sure that the grid knows that the rows and columns can grow.  The
        # image/movie panels live inside geometry-propagation-disabled frames
        # (see _panel) so their content cannot inflate their columns, which lets
        # these equal weights reproduce the proportions of the original wx
        # GridBagSizer (images 6 columns, description 2 columns).
        for i in range(iw+tw):
            container.grid_columnconfigure(i, weight=1)
        for i in range(1, ih+1):
            container.grid_rowconfigure(i, weight=1)

    def init_events(self):
        # Re-render images when their panels are resized
        self.latestImage.bind('<Configure>', self.update_latest_image)
        self.stationImage.bind('<Configure>', self.update_station_image)
        self.descriptionText.bind('<Configure>', lambda e: self.update_text_size())

        # Window manager close
        self.protocol('WM_DELETE_WINDOW', self.on_quit)

    def init_images(self):
        # Update the images, movie, and text
        self._fetching = False
        self.latestImageTime = 0.0
        self._latestQueue = queue.Queue()
        self._fetch_latest_async()      # first live image (in the background)
        self.update_station_image()
        self.update_image_description()

        # Start the recurring latest-image refresh and the queue drainer that
        # applies finished downloads back on the main thread
        self._latestJob = self.after(self._latest_interval(), self._tick_latest)
        self._drainJob = self.after(100, self._drain_latest)
        if not self.args.disable_movie:
            self.after(0, self.update_previous_movie)

    def _drain_latest(self):
        try:
            while True:
                result = self._latestQueue.get_nowait()
                self._apply_latest(*result)
        except queue.Empty:
            pass
        self._drainJob = self.after(100, self._drain_latest)

    def _latest_interval(self):
        return 200 if self.args.enable_fade else 5000

    def _tick_latest(self):
        # Kick off a fresh download when due (never blocks the event loop, so
        # the movie keeps playing), then re-render to drive the fade animation.
        if not self._fetching and time.time() - self.latestImageTime > 5:
            self._fetch_latest_async()
        self.update_latest_image()
        self._latestJob = self.after(self._latest_interval(), self._tick_latest)

    def on_quit(self, event=None):
        for attr in ('_latestJob', '_drainJob'):
            job = getattr(self, attr, None)
            if job is not None:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
        if not self.args.disable_movie:
            self.previousMovie.stop()
        self.destroy()

    def load_station_image(self):
        if self.args.lwatv4:
            path = os.path.join(self.imagePath, 'lwana.jpg')
        elif self.args.lwatv2:
            path = os.path.join(self.imagePath, 'lwasv.jpg')
        else:
            path = os.path.join(self.imagePath, 'lwa1.jpg')
        self.pilStationImage = PImage.open(path).convert('RGB')

    def _fetch_latest_async(self):
        # Download + decode on a worker thread so the network wait never stalls
        # the Tk event loop (which would freeze the appsink movie playback).
        self._fetching = True
        self.latestImageTime = time.time()

        def work():
            # Hand the result back through a thread-safe queue; the main-thread
            # drainer applies it (Tk must only be touched from the main thread).
            self._latestQueue.put(self._download_latest())

        threading.Thread(target=work, daemon=True).start()

    def _download_latest(self):
        # Runs on a worker thread: must not touch any Tk widgets.
        if self.args.lwatv4:
            url = f'https://lwalab.phys.unm.edu/lwatv4/lwatv.png?lwatvgui={time.time():.0f}'
        elif self.args.lwatv2:
            url = f'https://lwalab.phys.unm.edu/lwatv2/lwatv.png?lwatvgui={time.time():.0f}'
        else:
            url = f'https://lwalab.phys.unm.edu/lwatv/lwatv.png?lwatvgui={time.time():.0f}'

        log = f"Download at {url}"
        try:
            with urlopen(url) as fh:
                info = fh.info()
                data = fh.read()

            lm = info.get("last-modified")
            lm = datetime.strptime(lm, "%a, %d %b %Y %H:%M:%S GMT").replace(tzinfo=timezone.utc)
            age = datetime.now(tz=timezone.utc) - lm
            age = age.days*24*3600 + age.seconds

            # Is the image recent enough to think that the station is running?
            if age > 120:
                # Reachable, but stale -> the station is not currently running
                image = PImage.open(os.path.join(self.imagePath, 'error.png')).convert('RGB')
                return ("LWATV is not currently running",
                        image, f"{log} -> not currently running")

            image = PImage.open(BytesIO(data)).convert('RGB')
            if self.args.lwatv4:
                label = "Latest LWATV4 Image"
            elif self.args.lwatv2:
                label = "Latest LWATV2 Image"
            else:
                label = "Latest LWATV Image"
            return (label, image, log)

        except Exception:
            # Deal with network/download errors
            image = PImage.open(os.path.join(self.imagePath, 'error.png')).convert('RGB')
            return ("Network Connection Error", image, f"{log} -> error")

    def _apply_latest(self, labelText, image, log):
        # Runs back on the Tk main thread once the download finishes.
        if self.args.enable_fade and getattr(self, "pilLatestImage", None) is not None:
            self.pilLatestImageOld = self.pilLatestImage
        self.pilLatestImage = image
        if self.args.enable_fade:
            self.pilLatestImageTime = time.time()
        self.latestText.config(text=labelText)
        self._fetching = False

        if self.args.verbose:
            print(log)

        self.update_latest_image()

    def load_image_description(self):
        if self.args.lwatv4:
            descname = os.path.join(self.infoPath, 'lwatv4.txt')
        elif self.args.lwatv2:
            descname = os.path.join(self.infoPath, 'lwatv2.txt')
        else:
            descname = os.path.join(self.infoPath, 'lwatv.txt')
        with open(descname, 'r') as fh:
            self.imageDescription = fh.read()

    def _keep_aspect(self, size, widget):
        wi, hi = size
        wd, hd = widget.winfo_width(), widget.winfo_height()

        wr = 1.0*wd/wi
        hr = 1.0*hd/hi
        s = min([wr, hr])
        return int(round(wi*s)), int(round(hi*s))

    def _render_image(self, pil, widget):
        if widget.winfo_width() <= 1 or widget.winfo_height() <= 1:
            return
        w, h = self._keep_aspect(pil.size, widget)
        if w <= 0 or h <= 0:
            return
        image = pil.resize((w, h), RESAMPLE)
        photo = ImageTk.PhotoImage(image)
        widget.config(image=photo)
        widget.image = photo

    def update_station_image(self, event=None):
        if getattr(self, "pilStationImage", None) is None:
            self.load_station_image()
        self._render_image(self.pilStationImage, self.stationImage)

    def update_latest_image(self, event=None):
        # Render-only; the actual download happens asynchronously elsewhere.
        if getattr(self, "pilLatestImage", None) is None:
            return

        if self.args.enable_fade and getattr(self, "pilLatestImageOld", None) is not None \
                and time.time() - self.pilLatestImageTime < self.config['fadeTime']:
            alpha = (time.time() - self.pilLatestImageTime)/self.config['fadeTime']
            try:
                pil = PImage.blend(self.pilLatestImageOld, self.pilLatestImage, alpha)
            except ValueError:
                pil = self.pilLatestImage
        else:
            pil = self.pilLatestImage

        self._render_image(pil, self.latestImage)

    def update_previous_movie(self, event=None):
        self.previousMovie.advance()

    def update_image_description(self, event=None):
        if getattr(self, "imageDescription", None) is None:
            self.load_image_description()

        self.descriptionText.config(state='normal')
        self.descriptionText.delete('1.0', 'end')
        self.descriptionText.insert('1.0', self.imageDescription)
        self.descriptionText.config(state='disabled')
        self.after(0, self.update_text_size)

    def update_text_size(self):
        # Get the area of the text box
        w, h = self.descriptionText.winfo_width(), self.descriptionText.winfo_height()
        ta = w*h

        text = self.descriptionText.get('1.0', 'end-1c')
        if not text or ta <= 1:
            return

        # Find the "right" font size to use and use it.  The divisor is a
        # packing fudge factor: smaller -> larger text.
        def area2points(area, text):
            points = math.sqrt(area/(1.5*len(text)))
            points = math.floor(points)
            return int(points)
        self.descFont.configure(size=max(1, area2points(ta, text)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="GUI for displaying the contents of LWATV in an educational setting",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-f', '--enable-fade', action='store_true',
                        help='enable the LWATV latest image fade effect')
    parser.add_argument('-d', '--disable-movie', action='store_true',
                        help='disable playing old movies')
    parser.add_argument('-n', '--disable-maximize', action='store_true',
                        help='disable automatic maximization of the window')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='dislay GUI status messages')
    sgroup = parser.add_mutually_exclusive_group(required=False)
    sgroup.add_argument('-2', '--lwatv2', action='store_true',
                        help='show data from LWA-SV instead of LWA1')
    sgroup.add_argument('-4', '--lwatv4', action='store_true',
                        help='show data from LWA-NA instead of LWA1')
    args = parser.parse_args()

    # Check for movies
    basePath = os.path.dirname(os.path.abspath(__file__))
    moviePath = os.path.join(basePath, 'movies')
    movies = glob.glob(os.path.join(moviePath, '*.mov'))
    if len(movies) == 0:
        print("WARNING: No movies found under 'movies/', disabling movie panel.")
        print("         To enable the movie panel, run 'updateMovies.py' and   ")
        print("         restart this script.                                   ")
        args.disable_movie = True

    print(f"Starting {os.path.basename(__file__)} with PID {os.getpid()}")

    app = LWATV(args=args, config={'fadeTime': 1.5})
    app.mainloop()
