#!/bin/sh
# Name: The Myles Times
# Author: The Myles Times
# DontUseFBInk
#
# The only "book" you need: downloads today's edition and opens it.
# Offline? It opens the last edition you downloaded.

# One-time tidy-up: remove the setup-era launchers this replaces.
for old in mp1_info mp2_text mp3_page mp4_net mp5_fetch mp6_probe mp7_read; do
    rm -f "/mnt/us/documents/$old.sh"
done

/bin/sh /mnt/us/morningpaper/bin/fetch.sh >> /mnt/us/morningpaper/log.txt 2>&1
