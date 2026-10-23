#!/bin/sh
# Name: The Myles Times
# Author: The Myles Times
# DontUseFBInk
#
# The only "book" you need: downloads today's edition and opens it.
# Offline? It opens the last edition you downloaded.
# Also starts the morning daemon (paperd), which keeps running until a reboot.

# One-time tidy-up: remove the setup-era launchers this replaces.
for old in mp1_info mp2_text mp3_page mp4_net mp5_fetch mp6_probe mp7_read; do
    rm -f "/mnt/us/documents/$old.sh"
done

# Morning daemon: in its own session so it outlives this launcher.
if command -v setsid >/dev/null 2>&1; then
    setsid sh /mnt/us/morningpaper/bin/paperd.sh < /dev/null > /dev/null 2>&1 &
else
    sh /mnt/us/morningpaper/bin/paperd.sh < /dev/null > /dev/null 2>&1 &
fi

/bin/sh /mnt/us/morningpaper/bin/fetch.sh >> /mnt/us/morningpaper/log.txt 2>&1
