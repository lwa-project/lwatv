#!/bin/bash

# Build the RPi version of lwaTV3.py
cp ../lwaTV3.py lwaTV3.rpi.py
patch lwaTV3.rpi.py <convert3toRPi.patch
perms=`stat -c '%a' ../lwaTV3.py `
chmod ${perms} lwaTV3.rpi.py

# Build the RPi version of updateMovies.py
cp ../updateMovies.py updateMovies.py

