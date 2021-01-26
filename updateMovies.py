#!/usr/bin/env python3

"""
Simple script to update the list of pre-recorded movies used by the lwaTV.py 
script.
"""

import os
import sys
import glob
import math
import time
import argparse
from urllib.request import urlopen


# Number of days worth of movies to keep on hand for replaying
_DAYS_TO_STORE = 7


# Paths
_BASE_PATH = os.path.dirname(os.path.abspath(__file__))
_IMAGE_PATH = os.path.join(_BASE_PATH, 'images')
_MOVIE_PATH = os.path.join(_BASE_PATH, 'movies')


# Download chunk size
_CHUNK_SIZE = 1024**2


def main(args):
    if args.query:
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
            
        print("%i movies occupy %.1f MB of disk space" % (len(currentMovies), sum(sizes)/1024.0**2))
        for movie,size,age in zip(movies, sizes, ages):
            if age == 1:
                print("  %s @ %.1f MB -> %i day old" % (movie, size/1024.0**2, age))
            else:
                print("  %s @ %.1f MB -> %i days old" % (movie, size/1024.0**2, age))
                
    else:
        # Get the current MJD in order to figure out what can be downloaded
        tNow = time.time()
        jdNow = tNow/86400.0 + 2440587.5
        mjdNow = int(jdNow - 2400000.5)
        movieDownloadRange = ["%i.mov" % i for i in range(mjdNow-args.days,mjdNow)]
        
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
        if args.verbose:
            print("%i movie(s) will be deleted" % len(toDelete))
        for movie in toDelete:
            try:
                os.unlink(movie)
            except Exception as e:
                print("Error deleting %s: %s" % (os.path.basename(movie), str(e)))
                
        # ... in with the new
        if args.verbose:
            print("%i movie(s) will be downloaded" % len(toDownload))
        for movie in toDownload:
            if args.lwatv2:
                url = 'https://lwalab.phys.unm.edu/lwatv2/%s' % movie
            else:
                url = 'https://lwalab.phys.unm.edu/lwatv/%s' % movie
            if args.verbose:
                print("Downloading '%s'..." % url)
                
            try:
                dh = urlopen(url)
                fh = open(os.path.join(_MOVIE_PATH, movie), 'wb')
                while True:
                    data = dh.read(_CHUNK_SIZE)
                    if len(data) == 0:
                        break
                    fh.write(data)
                dh.close()
                fh.close()
            except Exception as e:
                print("Error with %s: %s" % (movie, str(e)))
                continue
                
        # Report on disk usage
        diskUsage = 0
        currentMovies = glob.glob(os.path.join(_MOVIE_PATH, '*.mov'))
        for movie in currentMovies:
            diskUsage += os.path.getsize(movie)
        if args.verbose:
            print("%i movies occupy %.1f MB of disk space" % (len(currentMovies), diskUsage/1024.0**2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="simple script to update the list of pre-recorded movies used by the lwaTV.py script",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-d', '--days', type=int, default=5,
                        help='number of days to cache')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='display status messages')
    parser.add_argument('-q', '--query', action='store_true',
                        help='query the cache')
    parser.add_argument('-2', '--lwatv2', action='store_true',
                        help='update movies from LWA-SV instead of LWA1')
    args = parser.parse_args()
    main(args)
    
