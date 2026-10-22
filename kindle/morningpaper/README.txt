MORNING PAPER - Kindle engine

This folder goes at the ROOT of the Kindle drive (/mnt/us/morningpaper).
The mp*.sh scriptlets go in the Kindle's "documents" folder.

Library "books":
  Morning Paper 1 - Device info       -> info.txt
  Morning Paper 2 - Show test text    -> draws message.txt
  Morning Paper 3 - Show front page   -> draws images/test_<screen>.png
  Morning Paper 4 - Network test      -> net.txt
  Morning Paper 5 - Fetch today's paper -> downloads from GitHub, draws it

Settings: paper.conf. Private repo token: paper.local.conf (never committed).
Problems? Check log.txt in this folder.
