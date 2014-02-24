#!/usr/bin/env python
# -*- coding: utf-8 -*-


"""
Version 3 of a GUI application to show LWATV (gstreamer 1.0).
"""

import os
import wx
import sys
import copy
import glob
import time
import getopt
import random
import urllib2
from datetime import datetime
from PIL import Image as PImage
try:
	from cStringIO import StringIO
except ImportError:
	from StringIO import StringIO
	
if sys.platform.startswith('linux'):
	import ctypes
	try:
		x11 = ctypes.cdll.LoadLibrary('libX11.so')
		x11.XInitThreads()
	except:
		pass
		
import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst
from gi.repository import GstVideo

GObject.threads_init()
Gst.init(None)


def usage(exitCode=None):
	print """%s - GUI for displaying the contents of LWATV in an educational setting.

Usage: %s [OPTIONS]

Options:
-h, --help              Display this help information
-f, --enable-fade       Enable the LWATV latest image fade effect
-d, --disable-movie     Disable playing old movies
-n, --disable-maximize  Disable automatic maximization of the window
-v, --verbose           Display GUI status messages
""" % (os.path.basename(__file__), os.path.basename(__file__))
	
	if exitCode is not None:
		sys.exit(exitCode)
	else:
		return True


def parseOptions(args):
	config = {}
	# Defaults
	config['fadeTime'] = 1.5						# Fade time between LWATV images
	config['enableFade'] = False					# Enable fading between LWATV images
	config['enableMovie'] = True					# Enable the display of pre-recorded movies
	config['enableMaximize'] = True				# Enable auto. window maximization on start
	config['verbose'] = False					# Enable print GUI status messages to the terminal
	config['imageQuality'] = wx.IMAGE_QUALITY_NORMAL 	# wxImage resampling quality
	
	# Read in a process the command line flags
	try:
		opts, args = getopt.getopt(args, "hfdnv", ["help", "enable-fade", "disable-movie", "disable-maximize", "verbose"])
	except getopt.GetoptError, err:
		# Print help information and exit:
		print str(err) # will print something like "option -a not recognized"
		usage(exitCode=2)
		
	 # Work through opts
	for opt, value in opts:
		if opt in ('-h', '--help'):
			usage(exitCode=0)
		elif opt in ('-f', '--enable-fade'):
			config['enableFade'] = True
		elif opt in ('-d', '--disable-movie'):
			config['enableMovie'] = False
		elif opt in ('-n' '--disable-maximize'):
			config['enableMaximize'] = False
		elif opt in ('-v', '--verbose'):
			config['verbose'] = True
		else:
			assert False
			
	# Check for movies
	basePath = os.path.dirname(os.path.abspath(__file__))
	moviePath = os.path.join(basePath, 'movies')
	movies = glob.glob(os.path.join(moviePath, '*.mov'))
	if len(movies) == 0:
		print "WARNING: No movies found under 'movies/', disabling movie panel."
		print "         To enable the movie panel, run 'updateMovies.py' and   "
		print "         restart this script.                                   "
		config['enableMovie'] = False
		
	# Return configuration
	return config


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
			print "Finished movie"
		self.pipeline.set_state(Gst.State.NULL)
		
	def on_error_message(self, bus, message):
		print "Error %s: %s" % message.parse_error()
		
	def on_sync_message(self, bus, message):
		if message.get_structure().get_name() == 'prepare-window-handle':
			message.src.set_property('force-aspect-ratio', True)
			message.src.set_window_handle(self.GetHandle())
			
	def get_movie(self):
		movies = glob.glob(os.path.join(self.moviePath, '*.mov'))
		movies.sort()
		movie = random.choice(movies)
		
		if self.verbose:
			print "Next movie is %s" % movie
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
	def __init__(self, parent, title, config={}):
		wx.Frame.__init__(self, parent, title=title, size=(1310, 840))
		
		# Configuration
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
		if self.config['enableMaximize']:
			self.Maximize()
			
		# Update
		self.initImages()
			
	def initUI(self):	
		panel = wx.Panel(self, -1)
		panel.SetForegroundColour(wx.WHITE)
		panel.SetBackgroundColour(wx.BLACK)
		
		sizer = wx.GridBagSizer(0, 0)
		ih = 6
		iw = 6
		tw = 2
		iflags = wx.EXPAND|wx.ALIGN_CENTER|wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT
		
		font = wx.SystemSettings_GetFont(wx.SYS_SYSTEM_FONT)
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
		sizer.Add(self.latestImage, (1, 0), (ih/2, iw), iflags|wx.BOTTOM, 4)
		
		# LWA1 Station Image
		if self.config['enableMovie']:
			siw = iw/2
		else:
			siw = iw
		## Label
		stationText = wx.StaticText(panel, label="The LWA1 Site Located By the VLA")
		stationText.SetFont(font)
		stationText.SetForegroundColour(wx.WHITE)
		stationText.SetBackgroundColour(wx.BLACK)
		sizer.Add(stationText, (2+ih, 0), (1, siw), wx.ALIGN_CENTER|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 4)
		## Image
		self.stationImage = wx.Panel(panel, -1)
		self.stationImage.SetBackgroundColour(wx.BLACK)
		self.stationImage.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)
		sizer.Add(self.stationImage, (2+ih/2, 0), (ih/2, siw), iflags, 4)
		
		if self.config['enableMovie']:
			# Previously Recorded Movies
			## Label
			self.movieText = wx.StaticText(panel, label="Previous Movies")
			self.movieText.SetFont(font)
			self.movieText.SetForegroundColour(wx.WHITE)
			self.movieText.SetBackgroundColour(wx.BLACK)
			sizer.Add(self.movieText, (2+ih, iw/2), (1, iw/2), wx.ALIGN_CENTER|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 4)
			## Movie
			self.previousMovie = MoviePlayer(panel, self.moviePath, self.movieText, self.config['verbose'])
			sizer.Add(self.previousMovie, (2+ih/2, iw/2), (ih/2, iw/2), iflags, 4)
			
		# Image Information
		## Label
		descriptionLabel = wx.StaticText(panel, label="Image Description")
		descriptionLabel.SetFont(font)
		descriptionLabel.SetForegroundColour(wx.WHITE)
		descriptionLabel.SetBackgroundColour(wx.BLACK)
		sizer.Add(descriptionLabel, (0, iw), (1, tw), wx.ALIGN_CENTER|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 4)
		## Content
		self.descriptionText =  wx.TextCtrl(panel, -1, "Image description here.", style=wx.TE_MULTILINE|wx.TE_READONLY)
		self.descriptionText.SetForegroundColour(wx.WHITE)
		self.descriptionText.SetBackgroundColour(wx.BLACK)
		sizer.Add(self.descriptionText, (1, iw), (ih, tw), wx.EXPAND|wx.ALL, 10)
		## LWA1 Label
		lwa1Label = wx.StaticText(panel, label="Copyright (c) 2014 The LWA Consortium")
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
		#if self.config['enableMovie']:
		#	self.previousMovie.Bind(wx.EVT_PAINT, self.previousMovie.Update)
			
		# Window manager close
		self.Bind(wx.EVT_CLOSE, self.onQuit)
		
		# Timers
		## Latest Image
		self.latestTimer = wx.Timer(self, LATEST_TIMER)
		wx.EVT_TIMER(self, LATEST_TIMER, self.updateLatestImage)
		if self.config['enableMovie']:
			## Movie changes
			self.movieTimer = wx.Timer(self, MOVIE_TIMER)
			wx.EVT_TIMER(self, MOVIE_TIMER, self.updatePreviousMovie)
			
	def initImages(self):
		# Update the images, movie, and text
		self.updateLatestImage()
		self.updateStationImage()
		self.updateImageDescription()
		
		# Start the timers
		if self.config['enableFade']:
			lift = 200
		else:
			lift = 5000
		self.latestTimer.Start(lift)
		if self.config['enableMovie']:
			self.movieTimer.Start(7000)
			
	def onSize(self, event):
		self.panel.Layout()
		self.Layout()
		self.panel.Update()
		self.Update()
		
		self.updateLatestImage()
		self.updateStationImage()
		
	def onPaint(self, event):
		self.panel.Layout()
		self.Layout()
		self.panel.Update()
		self.Update()
		
		self.updateLatestImage()
		self.updateStationImage()
		
	def onQuit(self, event):
		self.latestTimer.Stop()
		if self.config['enableMovie']:
			self.movieTimer.Stop()
			self.previousMovie.stop()
		self.Destroy()
		
	def loadStationImage(self):
		fh = open(os.path.join(self.imagePath, 'lwa1.jpg'), 'r')
		data = fh.read()
		fh.close()
		
		self.wxStationImage = wx.ImageFromStream(StringIO(data))
		
	def loadLatestImage(self):
		url = 'http://lwalab.phys.unm.edu/lwatv/lwatv.png?lwatvgui=%s' % int(time.time())
		urlAlt = 'http://lwalab.phys.unm.edu/lwatv/beamPointings.png?lwatvgui=%s' % int(time.time())
		
		latestResult = "Download at %s" % url
		try:
			# Try to get the latest image...
			fh = urllib2.urlopen(url)
			data = fh.read()
			fh.close()
			
			info = fh.info()
			lm = info.get("last-modified")
			lm = datetime.strptime(lm, "%a, %d %b %Y %H:%M:%S GMT")
			age = datetime.utcnow() - lm
			age = age.days*24*3600 + age.seconds
			
			# Is the image recent enough to think that TBN/PASI is running?
			if age > 120:
				fh = urllib2.urlopen(urlAlt)
				data = fh.read()
				fh.close()
				
				latestResult = latestResult+" -> PASI is not currently running"
				
				self.config['imageMode'] = 'Beams'
				self.latestText.SetLabel("Current Beam Pointings")
			else:
				self.config['imageMode'] = 'LWATV'
				self.latestText.SetLabel("Latest LWATV Image")
				
		except:
			# Deal with network/download errors
			fh = open(os.path.join(self.imagePath, 'error.png'), 'r')
			data = fh.read()
			fh.close()
			
			latestResult = latestResult+" -> error"
			self.latestText.SetLabel("Network Connection Error")
			
		if self.config['verbose']:
			print latestResult
		self.wxLatestImage = wx.ImageFromStream(StringIO(data))
		
		if self.config['enableFade']:
			self.pilLatestImageTime = time.time()
			self.pilLatestImage = PImage.open(StringIO(data))
			self.pilLatestImage = self.pilLatestImage.convert('RGB')
			
	def loadImageDescription(self):
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
		image = self.wxStationImage.Scale(w, h, self.config['imageQuality'])
		w2, h2 = self.stationImage.GetSize()
		image.Resize(self.stationImage.GetSize(), ((w2-w)/2, (h2-h)/2), 0, 0, 0)
		bitmap = wx.BitmapFromImage(image)
		
		dc = wx.AutoBufferedPaintDC(self.stationImage)
		dc.DrawBitmap(bitmap, 0, 0)
		
	def updateLatestImage(self, event=None, fade=False):
		oldMode = self.config['imageMode']
		
		if getattr(self, "wxLatestImage", None) is None:
			self.latestImageTime = time.time()
			self.loadLatestImage()
			if self.config['enableFade']:
				self.pilLatestImageOld = self.pilLatestImage
				
		if time.time() - self.latestImageTime > 5:
			self.latestImageTime = time.time()
			if self.config['enableFade']:
				self.pilLatestImageOld = self.pilLatestImage
			self.loadLatestImage()
			
		if self.config['enableFade']:
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
			wxImage.SetData(pilImage.tostring())
		else:
			wxImage = self.wxLatestImage
			
		w, h = self._keepAspect(wxImage, self.latestImage)
		image = wxImage.Scale(w, h, self.config['imageQuality'])
		w2, h2 = self.latestImage.GetSize()
		image.Resize(self.latestImage.GetSize(), ((w2-w)/2, (h2-h)/2), 0, 0, 0)
		bitmap = wx.BitmapFromImage(image)
		
		dc = wx.AutoBufferedPaintDC(self.latestImage)
		dc.DrawBitmap(bitmap, 0, 0)
		
		if oldMode != self.config['imageMode']:
			if self.config['verbose']:
				print "Image mode changed, triggering description update"
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


if __name__ == "__main__":
	# Parse the options
	config = parseOptions(sys.argv[1:])
	
	print "Starting %s with PID %i" % (os.path.basename(__file__), os.getpid())
	
	app = wx.App()
	LWATV(None, title="LWATV GUI", config=config)
	app.MainLoop()