import jukebox
import sys

# Where the playlist db is located
SQLITE_DB = "playlist.db"

# Debug flag for resetting the playlist db upon start
__RESET_SQLITE_DB = True

if __name__ == "__main__":
    visible = False
    if len(sys.argv) == 2 and sys.argv[1] == "--visible":
        visible = True
    jbox = jukebox.Jukebox(db=SQLITE_DB, reset_db=__RESET_SQLITE_DB, visible_host=visible)
    jbox.start_server()
