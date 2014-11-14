import os
import pdb
import json
import sqlite3 as sqlite
import threading
import cherrypy
import mpv
import collections
from ws4py.server.cherrypyserver import WebSocketPlugin, WebSocketTool, WebSocket
from youtube_dl import YoutubeDL

# load lua libs for mpv to play youtube urls directly w/o
# translation with youtube_dl
#mpv.load_lua()

PLAYLIST_SCHEMA = """
    CREATE TABLE playlist (
        plid integer primary key autoincrement,
        title TEXT,
        uri TEXT,
        votes INTEGER,
        next VARCHAR(50)
    )"""

def get_youtube_info(url):
    ydl = YoutubeDL()
    ydl.add_default_info_extractors()
    try:
        info = ydl.extract_info(url, download=False)
    except:
        return None
    return info

class Jukebox:
    
    def __init__(self, db=None, reset_db=False, ws_port=9000):
        if not db:
            raise NameError("Database not specified")

        if not os.path.isfile(db):
            # create db
            reset_db = True
        elif reset_db:
            os.remove(db)

        if reset_db:
            self.create_db(db)

        self.db_name = db
        self.ws_port = ws_port
        self.mpv = mpv.MPV(None, no_video='')
        self.lock = threading.Lock()
        self.mpv_user_change = False
        self.mpv_shutdown = False
        self.currently_playing = None

    def mpv_end_file(self):
        if not self.mpv_user_change:
            # get next plid
            conn = sqlite.connect(self.db_name)
            cursor = conn.execute(
                "SELECT next FROM playlist WHERE plid=?", (self.currently_playing,))
            res = cursor.fetchone()
            conn.close()
            if res is not None:
                new_plid = res[0]
                self._play(new_plid)
        with self.lock:
            self.mpv_user_change = False

    def create_db(self, db_name):
        conn = sqlite.connect(db_name)
        conn.execute(PLAYLIST_SCHEMA)
        conn.commit()
        conn.close()

    def start_server(self):
        # start mpv listeners
        self.mpv.register_event_callback(mpv.MpvEventID.END_FILE, self.mpv_end_file)

        # set web worker db access
        JukeboxWebWorker.pl_db = self.db_name
        # set web worker actions
        JukeboxWebWorker.jukebox_actions = {
            "play": self.play,
            "playpause": self.playpause,
            "volup": self.volup,
            "voldn": self.voldn
        }
        config = {
            '/rq': {
                'tools.websocket.on': True,
                'tools.websocket.handler_cls': JukeboxWebWorker
            }
        }
        cherrypy.config.update({'server.socket_port': self.ws_port})
        WebSocketPlugin(cherrypy.engine).subscribe()
        cherrypy.tools.websocket = WebSocketTool()

        cherrypy.engine.subscribe('stop', self.stop_server)

        cherrypy.quickstart(JukeboxWebService(), '/', config=config)

    def stop_server(self):
        # why isn't this working after Ctrl-C
        self.mpv_shutdown = True
        self.mpv.quit()

    def play(self, plid):
        ret = self._play(plid, user=True)
        if self.mpv.pause.val:
            self.mpv.pause = False
        return ret

    def _play(self, plid, user=False):
        with self.lock:
            self.mpv_user_change = self.currently_playing is not None and user

        uri = self.get_uri_from_id(plid)
        info = get_youtube_info(uri)
        if info is None:
            return False

        with self.lock:
            self.currently_playing = plid

        self.mpv.play(info["url"])
        return True

    def playpause(self):
        if self.mpv.pause.val:
            self.mpv.pause = False
        else:
            self.mpv.pause = True
        return True

    def volup(self):
        self.mpv.volume = min(5.0 + self.mpv.volume, self.mpv.volume)

    def voldn(self):
        self.mpv.volume = max(self.mpv.volume - 5.0, self.mpv.volume)

    def get_uri_from_id(self, plid):
        conn = sqlite.connect(self.db_name)
        cursor = conn.execute(
            "SELECT uri FROM playlist WHERE plid=?", (plid,))
        res = cursor.fetchone()
        conn.close()
        if res is None:
            return None
        return res[0]

class JukeboxWebService:
    def __init__(self):
        pass

    @cherrypy.expose
    def index(self):
        return "hello world"

    # this is the websocket endpoint
    @cherrypy.expose
    def rq(self):
        handler = cherrypy.request.ws_handler

class JukeboxWebWorker(WebSocket):
    # set by jukebox
    pl_db = None
    jukebox_actions = None

    def __init__(self, *args, **kwargs):
        super(JukeboxWebWorker, self).__init__(*args, **kwargs)
        #self.ydl = YoutubeDL({'restrictfilenames': True})
        #self.ydl.add_default_info_extractors()

    def msg_fail(self):
        self.send(json.dumps({'status':False,'rqid':self.rqid}))
    
    def msg_success(self, data={}):
        data.update({'status':True,'rqid':self.rqid})
        self.send(json.dumps(data))
    
    def received_message(self, message):
        self.rqid = None

        if message.is_binary:
            self.msg_fail()
            return

        try:
            msg = json.loads(str(message))
        except:
            self.msg_fail()
            return

        if not isinstance(msg, collections.Iterable):
            self.msg_fail()
            return

        if 'cmd' not in msg or 'rqid' not in msg:
            self.msg_fail()
            return

        self.rqid = msg["rqid"]

        cmd = msg["cmd"]
        if cmd == "add" and "uri" in msg:
            self.add_uri(msg["uri"])
        elif cmd == "playlist":
            pl = self.get_pl()
            self.msg_success(pl)
        elif cmd == "move_up" and "id" in msg:
            self.move_up(msg["id"])
        elif cmd == "play" and "id" in msg:
            if self.jukebox_actions["play"](msg["id"]):
                self.msg_success()
            else:
                self.msg_fail()
        elif cmd == "playpause":
            if self.jukebox_actions["playpause"]():
                self.msg_success()
            else:
                self.msg_fail()
        elif cmd == "volup":
            self.jukebox_actions["volup"]()
            self.msg_success()
        elif cmd == "voldn":
            self.jukebox_actions["voldn"]()
            self.msg_success()
        else:
            self.msg_fail()

    def add_uri(self,uri):
        info = get_youtube_info(uri)
        if info is None:
            self.msg_fail()
            return

        # deal with playlists
        if 'entries' in info:
            return

        try:
            # exclusive db connection
            conn = sqlite.connect(self.pl_db, isolation_level="EXCLUSIVE")

            # insert selection
            plrow = (info['title'], info['webpage_url'], 0)
            conn.execute("INSERT INTO playlist VALUES (null,?,?,?,null)", plrow)

            # update last element of linked list
            cursor = conn.execute(
                """UPDATE playlist SET next=last_insert_rowid()
                    WHERE next IS NULL
                    AND plid IS NOT last_insert_rowid()""")

            conn.commit()
            conn.close()
        except:
            self.msg_fail()
        else:
            pl = self.get_pl()
            cherrypy.engine.publish('websocket-broadcast', json.dumps(pl))
            self.msg_success()

    def move_up(self, plid):
        try:
            conn = sqlite.connect(self.pl_db, isolation_level="EXCLUSIVE")
            
            prev_cursor = conn.execute(
                "SELECT plid FROM playlist WHERE next=?", (plid,))
            prev_cursor_res = prev_cursor.fetchone()
            if prev_cursor_res is not None:
                prev_plid = prev_cursor_res[0]
                conn.execute(
                    """UPDATE playlist SET next=(
                        SELECT next FROM playlist WHERE plid=?)
                        WHERE plid=?""", (plid, prev_plid))
                conn.execute(
                    """UPDATE playlist SET next=?
                        WHERE plid=(
                        SELECT plid WHERE next=?)""", (plid, prev_plid))
                conn.execute(
                    """UPDATE playlist SET next=?
                        WHERE plid=?""", (prev_plid, plid))
                conn.commit()
            conn.close()
        except:
            self.msg_fail()
        else:
            pl = self.get_pl()
            cherrypy.engine.publish('websocket-broadcast', json.dumps(pl))
            self.msg_success()

    def get_pl(self):
        conn = sqlite.connect(self.pl_db)
        pl = []
        for row in conn.execute("SELECT * FROM playlist"):
            pl.append(
                {
                    'id': row[0],
                    'title': row[1],
                    'uri': row[2],
                    'votes': row[3],
                    'next': row[4]
                }
            )
        conn.close()

        msg = {
            'playlist': pl
        }
        return msg
