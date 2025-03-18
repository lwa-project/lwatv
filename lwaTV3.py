#!/usr/bin/env python3

"""
Version 3 of a GUI application to show LWATV (gstreamer 1.0).
"""

import os
import wx
import sys
import copy
import glob
import math
import time
import random
import argparse
from urllib.request import urlopen
from datetime import datetime
from PIL import Image as PImage
from io import BytesIO

os.environ['WXSUPPRESS_SIZER_FLAGS_CHECK'] = '1'

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
from gi.repository import GObject, Gst
from gi.repository import GstVideo

GObject.threads_init()
Gst.init(None)

# Deal with the different wxPython versions
if 'phoenix' in wx.PlatformInfo:
    EnableLogging = wx.Log.EnableLogging
    ClientDC = wx.ClientDC
    Image = wx.Image
    Bitmap = wx.Bitmap
else:
    EnableLogging = wx.Log_EnableLogging
    ClientDC = wx.AutoBufferedPaintDC
    Image = wx.ImageFromStream
    Bitmap = wx.BitmapFromImage


class MoviePlayer(wx.Panel):
    """
    wx.Panel object to deal with playing the old movies.
    
    Based on:
        Example 2.2 http://pygstdocs.berlios.de/pygst-tutorial/playbin.html
    """
    
    def __init__(self, parent, moviePath, label, verbose=False):
        super(MoviePlayer, self).__init__(parent, -1, style=wx.EXPAND)
        
        self.moviePath = moviePath
        self.label = label
        self.verbose = verbose
        self.SetBackgroundColour(wx.BLACK)
        self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)
        
        self.pipeline = Gst.Pipeline()
        self.player = Gst.ElementFactory.make("playbin", None)
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.enable_sync_message_emission()
        bus.connect('message::eos', self.on_eos_message)
        bus.connect('message::error', self.on_error_message)
        bus.connect('sync-message::element', self.on_sync_message)
        self.pipeline.add(self.player)
        if sys.platform == 'darwin':
            vs = Gst.ElementFactory.make("ximagesink", None)
            self.player.set_property("video-sink", vs)
            
    def on_eos_message(self, bus, message):
        if self.verbose:
            print("Finished movie")
        self.pipeline.set_state(Gst.State.NULL)
        
        self.update()
        
    def on_error_message(self, bus, message):
        err, debug = message.parse_error()
        print("Error %s: %s" % (err, debug))
        
        self.pipeline.set_state(Gst.State.NULL)
        wx.CallAfter(self.update)
        
    def on_sync_message(self, bus, message):
        if message.get_structure().get_name() == 'prepare-window-handle':
            message.src.set_property('force-aspect-ratio', True)
            message.src.set_window_handle(self.GetHandle())
            
    def get_movie(self):
        movies = glob.glob(os.path.join(self.moviePath, '*.mov'))
        movies.sort()
        movie = random.choice(movies)
        
        if self.verbose:
            print("Next movie is %s" % movie)
        return movie
        
    def update(self):
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
            dt = datetime.utcfromtimestamp(t)
            mn = dt.strftime("%B")
            dy = int(dt.strftime("%d"))
            yr = int(dt.strftime("%Y"))
            datestr = "%s %i, %i" % (mn, dy, yr)
            self.label.SetLabel("Movie for %s" % datestr)		
            
            self.pipeline.set_state(Gst.State.NULL)
            self.player.set_property('uri', "file://%s" % movie)
            self.pipeline.set_state(Gst.State.PLAYING)
            
    def stop(self):
        self.pipeline.set_state(Gst.State.NULL)


LATEST_TIMER = 101
MOVIE_TIMER = 102

class LWATV(wx.Frame):
    def __init__(self, parent, title, args, config={}):
        wx.Frame.__init__(self, parent, title=title, size=(1310, 840))
        
        # Configuration
        self.args = args
        self.config = config
        self.config['imageMode'] = ''
        
        # Paths
        basePath = os.path.dirname(os.path.abspath(__file__))
        self.infoPath = os.path.join(basePath, 'info')
        self.imagePath = os.path.join(basePath, 'images')
        self.moviePath = os.path.join(basePath, 'movies')
        
        # Build the images
        self.initUI()
        self.initEvents()
        self.Show()
        if not self.args.disable_maximize:
            self.Maximize()
            
        # Update
        self.initImages()
        self.updateTextSize()
        
    def initUI(self):	
        panel = wx.Panel(self, -1)
        panel.SetForegroundColour(wx.WHITE)
        panel.SetBackgroundColour(wx.BLACK)
        
        sizer = wx.GridBagSizer(0, 0)
        ih = 6
        iw = 6
        tw = 2
        iflags = wx.EXPAND|wx.ALIGN_CENTER|wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT
        
        font = wx.SystemSettings.GetFont(wx.SYS_SYSTEM_FONT)
        font.SetPointSize(font.GetPointSize()+2)
        
        # Latest LWATV Image
        ## Label
        self.latestText = wx.StaticText(panel, label="Latest LWATV Image")
        self.latestText.SetFont(font)
        self.latestText.SetForegroundColour(wx.WHITE)
        self.latestText.SetBackgroundColour(wx.BLACK)
        sizer.Add(self.latestText, (0, 0), (1, iw), wx.ALIGN_CENTER|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 4)
        ## Image
        self.latestImage = wx.Panel(panel, -1)
        self.latestImage.SetBackgroundColour(wx.BLACK)
        self.latestImage.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)
        sizer.Add(self.latestImage, (1, 0), (ih//2, iw), iflags|wx.BOTTOM, 4)
        
        # LWA1 Station Image
        if not self.args.disable_movie:
            siw = iw//2
        else:
            siw = iw
        ## Label
        if self.args.lwatv2:
            stationText = wx.StaticText(panel, label="The LWA-SV Site Located on the Sevilleta NWR")
        else:
            stationText = wx.StaticText(panel, label="The LWA1 Site Located By the VLA")
        stationText.SetFont(font)
        stationText.SetForegroundColour(wx.WHITE)
        stationText.SetBackgroundColour(wx.BLACK)
        sizer.Add(stationText, (2+ih, 0), (1, siw), wx.ALIGN_CENTER|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 4)
        ## Image
        self.stationImage = wx.Panel(panel, -1)
        self.stationImage.SetBackgroundColour(wx.BLACK)
        self.stationImage.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)
        sizer.Add(self.stationImage, (2+ih//2, 0), (ih//2, siw), iflags, 4)
        
        if not self.args.disable_movie:
            # Previously Recorded Movies
            ## Label
            self.movieText = wx.StaticText(panel, label="Previous Movies")
            self.movieText.SetFont(font)
            self.movieText.SetForegroundColour(wx.WHITE)
            self.movieText.SetBackgroundColour(wx.BLACK)
            sizer.Add(self.movieText, (2+ih, iw//2), (1, iw//2), wx.ALIGN_CENTER|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 4)
            ## Movie
            self.previousMovie = MoviePlayer(panel, self.moviePath, self.movieText, self.args.verbose)
            sizer.Add(self.previousMovie, (2+ih//2, iw//2), (ih//2, iw//2), iflags, 4)
            
        # Image Information
        ## Label
        descriptionLabel = wx.StaticText(panel, label="Image Description")
        descriptionLabel.SetFont(font)
        descriptionLabel.SetForegroundColour(wx.WHITE)
        descriptionLabel.SetBackgroundColour(wx.BLACK)
        sizer.Add(descriptionLabel, (0, iw), (1, tw), wx.ALIGN_CENTER|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 4)
        ## Content
        self.descriptionText =  wx.TextCtrl(panel, -1, "Image description here.", style=wx.TE_MULTILINE|wx.TE_READONLY)
        if sys.platform != 'darwin':
            self.descriptionText.SetForegroundColour(wx.WHITE)
            self.descriptionText.SetBackgroundColour(wx.BLACK)
        sizer.Add(self.descriptionText, (1, iw), (ih, tw), wx.EXPAND|wx.ALL, 10)
        ## LWA1 Label
        lwa1Label = wx.StaticText(panel, label="Copyright (c) 2025 The LWA Consortium")
        lwa1Label.SetForegroundColour(wx.WHITE)
        lwa1Label.SetBackgroundColour(wx.BLACK)
        sizer.Add(lwa1Label, (2+ih, iw), (1, tw), wx.ALIGN_CENTER|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 4)
        
        # Make sure that the sizer knows that the rows and columns can grow
        for i in range(iw+tw):
            sizer.AddGrowableCol(i)
        for i in range(1, ih+1):
            sizer.AddGrowableRow(i)
            
        sizer2 = wx.BoxSizer(wx.VERTICAL)
        sizer2.Add(sizer, 1, wx.EXPAND|wx.ALIGN_CENTER|wx.ALIGN_CENTER_VERTICAL, 0)
        panel.SetSizer(sizer2)
        panel.Layout()
        self.panel = panel
        
        sizer3 = wx.BoxSizer(wx.VERTICAL)
        sizer3.Add(panel, 1, wx.EXPAND|wx.ALIGN_CENTER|wx.ALIGN_CENTER_VERTICAL, 0)
        self.SetSizer(sizer3)
        self.Layout()
        
    def initEvents(self):
        # Resize and repaint events
        self.Bind(wx.EVT_SIZE, self.onSize)
        self.Bind(wx.EVT_PAINT, self.onPaint)
        self.latestImage.Bind(wx.EVT_PAINT, self.onPaint)
        self.stationImage.Bind(wx.EVT_PAINT, self.onPaint)
        
        # Window manager close
        self.Bind(wx.EVT_CLOSE, self.onQuit)
        
        # Timers
        ## Latest Image
        self.latestTimer = wx.Timer(self, LATEST_TIMER)
        self.Bind(wx.EVT_TIMER, self.updateLatestImage)
        
    def initImages(self):
        # Update the images, movie, and text
        self.updateLatestImage()
        self.updateStationImage()
        self.updateImageDescription()
        
        # Start the timers
        if self.args.enable_fade:
            lift = 200
        else:
            lift = 5000
        self.latestTimer.Start(lift)
        if not self.args.disable_movie:
            wx.CallAfter(self.updatePreviousMovie)
            
    def onSize(self, event):
        self.panel.Layout()
        self.Layout()
        self.panel.Update()
        self.Update()
        
        self.updateLatestImage()
        self.updateStationImage()
        self.updateTextSize()
        
    def onPaint(self, event):
        self.panel.Update()
        self.Update()
        
        self.updateLatestImage()
        self.updateStationImage()
        
    def onQuit(self, event):
        self.latestTimer.Stop()
        if not self.args.disable_movie:
            self.previousMovie.stop()
        self.Destroy()
        
    def loadStationImage(self):
        if self.args.lwatv2:
            fh = open(os.path.join(self.imagePath, 'lwasv.jpg'), 'rb')
        else:
            fh = open(os.path.join(self.imagePath, 'lwa1.jpg'), 'rb')
        data = fh.read()
        fh.close()
        
        self.wxStationImage = Image(BytesIO(data))
        
    def loadLatestImage(self):
        if self.args.lwatv2:
            url = 'https://lwalab.phys.unm.edu/lwatv2/lwatv.png?lwatvgui=%s' % int(time.time())
            urlAlt = 'https://lwalab.phys.unm.edu/lwatv2/beamPointings.png?lwatvgui=%s' % int(time.time())
        else:
            url = 'https://lwalab.phys.unm.edu/lwatv/lwatv.png?lwatvgui=%s' % int(time.time())
            urlAlt = 'https://lwalab.phys.unm.edu/lwatv/beamPointings.png?lwatvgui=%s' % int(time.time())
        
        latestResult = "Download at %s" % url
        try:
            # Try to get the latest image...
            fh = urlopen(url)
            data = fh.read()
            fh.close()
            
            info = fh.info()
            lm = info.get("last-modified")
            lm = datetime.strptime(lm, "%a, %d %b %Y %H:%M:%S GMT")
            age = datetime.utcnow() - lm
            age = age.days*24*3600 + age.seconds
            
            # Is the image recent enough to think that TBN/PASI is running?
            if age > 120:
                fh = urlopen(urlAlt)
                data = fh.read()
                fh.close()
                
                latestResult = latestResult+" -> LASI is not currently running"
                
                self.config['imageMode'] = 'Beams'
                self.latestText.SetLabel("Current Beam Pointings")
            else:
                self.config['imageMode'] = 'LWATV'
                if self.args.lwatv2:
                    self.latestText.SetLabel("Latest LWATV2 Image")
                else:
                    self.latestText.SetLabel("Latest LWATV Image")
                
        except:
            # Deal with network/download errors
            fh = open(os.path.join(self.imagePath, 'error.png'), 'r')
            data = fh.read()
            fh.close()
            
            latestResult = latestResult+" -> error"
            self.latestText.SetLabel("Network Connection Error")
            
        if self.args.verbose:
            print(latestResult)
        self.wxLatestImage = Image(BytesIO(data))
        
        if self.args.enable_fade:
            self.pilLatestImageTime = time.time()
            self.pilLatestImage = PImage.open(BytesIO(data))
            self.pilLatestImage = self.pilLatestImage.convert('RGB')
            
    def loadImageDescription(self):
        if self.args.lwatv2:
            fh = open(os.path.join(self.infoPath, 'lwatv2.txt'))
        else:
            fh = open(os.path.join(self.infoPath, 'lwatv.txt'))
        data1 = fh.read()
        fh.close()
        
        fh = open(os.path.join(self.infoPath, 'beams.txt'))
        data2 = fh.read()
        fh.close()
        
        self.imageDescriptionLWATV = data1
        self.imageDescriptionBeams = data2
        
    def _keepAspect(self, image, panel):
        wi,hi = image.GetSize()
        wd,hd = panel.GetSize()
        
        wr = 1.0*wd/wi
        hr = 1.0*hd/hi
        s = min([wr, hr])
        return int(round(wi*s)), int(round(hi*s))
        
    def updateStationImage(self, event=None):
        if getattr(self, "wxStationImage", None) is None:
            self.loadStationImage()
            
        w, h = self._keepAspect(self.wxStationImage, self.stationImage)
        image = self.wxStationImage.Scale(w, h, wx.IMAGE_QUALITY_NORMAL)
        w2, h2 = self.stationImage.GetSize()
        image.Resize(self.stationImage.GetSize(), ((w2-w)//2, (h2-h)//2), 0, 0, 0)
        bitmap = Bitmap(image)
        
        dc = ClientDC(self.stationImage)
        dc.DrawBitmap(bitmap, 0, 0)
        
    def updateLatestImage(self, event=None, fade=False):
        oldMode = self.config['imageMode']
        
        if getattr(self, "wxLatestImage", None) is None:
            self.latestImageTime = time.time()
            self.loadLatestImage()
            if self.args.enable_fade:
                self.pilLatestImageOld = self.pilLatestImage
                
        if time.time() - self.latestImageTime > 5:
            self.latestImageTime = time.time()
            if self.args.enable_fade:
                self.pilLatestImageOld = self.pilLatestImage
            self.loadLatestImage()
            
        if self.args.enable_fade:
            if time.time()-self.pilLatestImageTime < self.config['fadeTime']:
                alpha = (time.time() - self.pilLatestImageTime)/self.config['fadeTime']
                try:
                    pilImage = PImage.blend(self.pilLatestImageOld, self.pilLatestImage, alpha)
                    pilImage = pilImage.convert('RGB')
                except ValueError:
                    pilImage = self.pilLatestImage
            else:
                pilImage = self.pilLatestImage
                
            # Convert to wxImage
            wxImage = wx.EmptyImage( *pilImage.size  )
            wxImage.SetData(pilImage.tobytes())
        else:
            wxImage = self.wxLatestImage
            
        w, h = self._keepAspect(wxImage, self.latestImage)
        image = wxImage.Scale(w, h, wx.IMAGE_QUALITY_NORMAL)
        w2, h2 = self.latestImage.GetSize()
        image.Resize(self.latestImage.GetSize(), ((w2-w)//2, (h2-h)//2), 0, 0, 0)
        bitmap = Bitmap(image)
        
        dc = ClientDC(self.latestImage)
        dc.DrawBitmap(bitmap, 0, 0)
        
        if oldMode != self.config['imageMode']:
            if self.args.verbose:
                print("Image mode changed, triggering description update")
            wx.CallAfter(self.updateImageDescription)
            
    def updatePreviousMovie(self, event=None):
        self.previousMovie.update()
        
    def updateImageDescription(self, event=None):
        if getattr(self, "imageDescriptionLWATV", None) is None:
            self.loadImageDescription()
            
        if self.config['imageMode'] == 'LWATV':
            self.descriptionText.SetValue(self.imageDescriptionLWATV)
        else:
            self.descriptionText.SetValue(self.imageDescriptionBeams)
        wx.CallAfter(self.updateTextSize)
        
    def updateTextSize(self):
        # Get the area of the text box
        w,h = self.descriptionText.GetSize()
        ta = w*h
        
        # Get the base font
        font = wx.SystemSettings.GetFont(wx.SYS_SYSTEM_FONT)
        
        # Find the "right" font size to use and use it
        def area2points(area, text):
            points = math.sqrt(area/(1.5*len(text)))
            points = math.floor(points)
            return int(points)
        font.SetPointSize( area2points(ta, self.descriptionText.GetValue()) )
        self.descriptionText.SetFont(font)


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
    parser.add_argument('-2', '--lwatv2', action='store_true',
                        help='show data from LWA-SV instead of LWA1')
    args = parser.parse_args()
    
    # Check for movies
    basePath = os.path.dirname(os.path.abspath(__file__))
    moviePath = os.path.join(basePath, 'movies')
    movies = glob.glob(os.path.join(moviePath, '*.mov'))
    if len(movies) == 0:
        print("WARNING: No movies found under 'movies/', disabling movie panel.")
        print("         To enable the movie panel, run 'updateMovies.py' and   ")
        print("         restart this script.                                   ")
        args.disable_movies = True
        
    print("Starting %s with PID %i" % (os.path.basename(__file__), os.getpid()))
    
    # Suppress various error popups
    EnableLogging(False)
    
    app = wx.App()
    LWATV(None, title="LWATV GUI", args=args, config={'fadeTime': 1.5})
    app.MainLoop()
