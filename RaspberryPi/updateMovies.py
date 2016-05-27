#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Simple script to update the list of pre-recorded movies used by the lwaTV.py 
script.
"""

import os
import sys
import glob
import math
import time
import getopt
import urllib2


# Number of days worth of movies to keep on hand for replaying
_DAYS_TO_STORE = 7


# Paths
_BASE_PATH = os.path.dirname(os.path.abspath(__file__))
_IMAGE_PATH = os.path.join(_BASE_PATH, 'images')
_MOVIE_PATH = os.path.join(_BASE_PATH, 'movies')


# Download chunk size
_CHUNK_SIZE = 1024**2


def usage(exitCode=None):
	print """updateMovies.py - Refresh the on-disk LWATV movie cache

Usage: updateMovies.py [OPTIONS]

Options:
-h, --help              Display this help information
-d, --days              Number of days to cache (default = 7)
-v, --verbose           Display status messages
-q, --query             Query the cache
-2, --lwatv2            Update movies from LWA-SV (default is LWA1)
"""
	
	if exitCode is not None:
		sys.exit(exitCode)
	else:
		return True


def parseOptions(args):
	config = {}
	# Defaults
	config['daysToCache'] = 7		# Days worth of movies to cache
	config['verbose'] = False		# Enable print status messages to the terminal
	config['queryCache'] = False		# Query the current disk cache
	config['station'] = 'LWA1'		# Which station to show data from
	
	# Read in a process the command line flags
	try:
		opts, args = getopt.getopt(args, "hd:vq", ["help", "days=", "verbose", "query"])
	except getopt.GetoptError, err:
		# Print help information and exit:
		print str(err) # will print something like "option -a not recognized"
		usage(exitCode=2)
		
	 # Work through opts
	for opt, value in opts:
		if opt in ('-h', '--help'):
			usage(exitCode=0)
		elif opt in ('-d', '--days'):
			config['daysToCache'] = int(value)
		elif opt in ('-v', '--verbose'):
			config['verbose'] = True
		elif opt in('-q', '--query'):
			config['queryCache'] = True
		elif opt in ('-2', '--lwatv2'):
			config['station'] = 'LWA-SV'
		else:
			assert False
			
	# Return configuration
	return config


def main(args):
	# Parse the configuration
	config = parseOptions(args)
	
	if config['queryCache']:
		# Report on disk usage
		movies = []
		ages = []
		sizes = []
		currentMovies = glob.glob(os.path.join(_MOVIE_PATH, '*.mov'))
		currentMovies.sort()
		for movie in currentMovies:
			movies.append( os.path.basename(movie) )
			
			age = movies[-1].split('.', 1)[0]
			age = int(age) + 2400000.5
			age = (age - 2440587.5)*86400.0
			age = time.time() - age
			age = int(age/86400.0)
			ages.append(age)
			
			sizes.append( os.path.getsize(movie) )
			
		print "%i movies occupy %.1f MB of disk space" % (len(currentMovies), sum(sizes)/1024.0**2)
		for movie,size,age in zip(movies, sizes, ages):
			if age == 1:
				print "  %s @ %.1f MB -> %i day old" % (movie, size/1024.0**2, age)
			else:
				print "  %s @ %.1f MB -> %i days old" % (movie, size/1024.0**2, age)
				
	else:
		# Get the current MJD in order to figure out what can be downloaded
		tNow = time.time()
		jdNow = tNow/86400.0 + 2440587.5
		mjdNow = int(jdNow - 2400000.5)
		movieDownloadRange = ["%i.mov" % i for i in xrange(mjdNow-config['daysToCache'],mjdNow)]
		
		# Get the list of movies currently in the movie directory
		currentMovies = glob.glob(os.path.join(_MOVIE_PATH, '*.mov'))
		
		# Figure out which ones need to be expunged due to age
		toDelete = []
		for movie in currentMovies:
			movieBase = os.path.basename(movie)
			if movieBase not in movieDownloadRange:
				toDelete.append(movie)
				
		# Figure out which movies are missing from the directory
		toDownload = []
		for movie in movieDownloadRange:
			movieFull = os.path.join(_MOVIE_PATH, movie)
			if movieFull not in currentMovies:
				toDownload.append(movie)
				
		# Out with the old...
		if config['verbose']:
			print "%i movie(s) will be deleted" % len(toDelete)
		for movie in toDelete:
			try:
				os.unlink(movie)
			except Exception, e:
				print "Error deleting %s: %s" % (os.path.basename(movie), str(e))
				
		# ... in with the new
		if config['verbose']:
			print "%i movie(s) will be downloaded" % len(toDownload)
		for movie in toDownload:
			if config['station'] == 'LWA-SV':
				url = 'http://lwalab.phys.unm.edu/lwatv2/%s' % movie
			else:
				url = 'http://lwalab.phys.unm.edu/lwatv/%s' % movie
			if config['verbose']:
				print "Downloading '%s'..." % url
				
			try:
				dh = urllib2.urlopen(url)
				fh = open(os.path.join(_MOVIE_PATH, movie), 'wb')
				while True:
					data = dh.read(_CHUNK_SIZE)
					if len(data) == 0:
						break
					fh.write(data)
				dh.close()
				fh.close()
			except Exception, e:
				print "Error with %s: %s" % (movie, str(e))
				continue
				
		# Report on disk usage
		diskUsage = 0
		currentMovies = glob.glob(os.path.join(_MOVIE_PATH, '*.mov'))
		for movie in currentMovies:
			diskUsage += os.path.getsize(movie)
		if config['verbose']:
			print "%i movies occupy %.1f MB of disk space" % (len(currentMovies), diskUsage/1024.0**2)


if __name__ == "__main__":
	main(sys.argv[1:])
