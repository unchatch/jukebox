import jukebox

# Where the playlist db is located
SQLITE_DB = "playlist.db"

# Debug flag for resetting the playlist db upon start
__RESET_SQLITE_DB = True

if __name__ == "__main__":
    jbox = jukebox.Jukebox(db=SQLITE_DB, reset_db=__RESET_SQLITE_DB)
    jbox.start_server()
