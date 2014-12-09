import os
import sys
import pdb
import json
import threading
import cherrypy
import mpv
import time
import queue
from ws4py.server.cherrypyserver import WebSocketPlugin, WebSocketTool, WebSocket
from ws4py.client import WebSocketBaseClient
from youtube_dl import YoutubeDL

# load lua libs for mpv to play youtube urls directly w/o
# translation with youtube_dl
#mpv.load_lua()

# debug flag
DEBUG = False

# Where the playlist file is located
PLAYLIST_FILE = "playlist.json"

# WS Port
WS_PORT = 9000

# host visibility
VISIBILITY = False

def debug(msg):
    if DEBUG:
        print(">> DEBUG: ", msg)

def get_youtube_info(url):
    ydl = YoutubeDL()
    ydl.add_default_info_extractors()
    try:
        info = ydl.extract_info(url, download=False)
    except:
        return None
    return info

def broadcast(payload, label):
    msg = {
        "label": label,
        "type": "broadcast",
        "payload": payload
    }
    cherrypy.engine.publish("websocket-broadcast", json.dumps(msg))

class JukeboxWebService:
    @cherrypy.expose
    def rq(self):
        handler = cherrypy.request.ws_handler

class Jukebox:
    @classmethod
    def start_server(cls):
        if os.path.isfile(PLAYLIST_FILE):
            f = open(PLAYLIST_FILE, "r")
            try:
                cls.playlist = json.loads(f.read())
            except:
                pass
            finally:
                f.close()
        else:
            cls.playlist = []
        
        cls.currently_playing = None
        cls.user_selected_flag = False
        cls.shutdown_flag = False
        cls.lock = threading.Lock()
        cls.mpv = mpv.MPV(None, no_video='')
        cls.volume = 100.0

        # threaded debug
        if DEBUG:
            cls._thread_debug = threading.Thread(target=cls._debug)
            cls._thread_debug.start()

        # threaded broadcast of position
        cls._thread_broadcast_pos = threading.Thread(target=cls._broadcast_position)
        cls._thread_broadcast_pos.start()

        # start mpv listeners
        cls.mpv.register_event_callback(mpv.MpvEventID.END_FILE, cls._mpv_eof)

        # set mpv to paused initially
        cls.mpv.pause = True

        cherrypy_config = {
            "/rq": {
                "tools.websocket.on": True,
                "tools.websocket.handler_cls": JukeboxWebWorker
            }
        }
        cherrypy.config.update({"server.socket_port": WS_PORT})
        if VISIBILITY:
            cherrypy.config.update({"server.socket_host": "0.0.0.0"})

        WebSocketPlugin(cherrypy.engine).subscribe()
        cherrypy.tools.websocket = WebSocketTool()

        cherrypy.engine.subscribe("stop", cls.stop_server)

        cherrypy.quickstart(JukeboxWebService(), "/", config=cherrypy_config)

    @classmethod
    def _debug(cls):
        pdb.set_trace()

    @classmethod
    def _mpv_eof(cls):
        if not cls.user_selected_flag and cls.currently_playing is not None:
            cls._play(cls.currently_playing + 1)

    @classmethod
    def _broadcast_position(cls):
        while not cls.shutdown_flag:
            if cls.currently_playing is not None and not cls.mpv.pause.val:
                broadcast(cls.mpv.percent_pos, "position")
            # wait 1 sec before update
            time.sleep(1)

    @classmethod
    def stop_server(cls):
        cls.shutdown_flag = True
        cls.mpv.quit()

    @classmethod
    def _save_playlist(cls):
        f = open(PLAYLIST_FILE, "w")
        f.write(json.dumps(cls.playlist))
        f.close()

    @classmethod
    def _set_current(cls, current):
        with cls.lock:
            cls.currently_playing = current
        broadcast(cls.currently_playing, "current")

    @classmethod
    def add_handler(cls, uri):
        info = get_youtube_info(uri)
        if info is None:
            return False

        # temporarily ingore playlists
        if "entries" in info:
            return False

        with cls.lock:
            # I think list append is protected by CPython's GIL
            cls.playlist.append({
                "title": info["title"],
                "url": info["webpage_url"]
            })
        cls._save_playlist()
        return True

    @classmethod
    def remove_handler(cls, sid):
        if sid >= len(cls.playlist):
            return False

        del cls.playlist[sid]
        cls._save_playlist()

        # stop if already playing
        if sid == cls.currently_playing:
            # play nothing and pause
            cls._set_paused(True)
            cls.mpv.play("")
            cls._set_current(None)
        # take care of adjusting currently_playing
        elif sid < cls.currently_playing:
            cls._set_current(cls.currently_playing-1)

        return True

    @classmethod
    def play_handler(cls, sid):
        if sid is None:
            return False
        with cls.lock:
            cls.user_selected_flag = True
        return cls._play(sid)

    @classmethod
    def _play(cls, sid):
        # unpause
        if cls.mpv.pause.val is True:
            cls._set_paused(False)
        
        if sid >= len(cls.playlist):
            return False

        info = get_youtube_info(cls.playlist[sid]["url"])
        if info is None:
            return False

        # set currently playing
        cls._set_current(sid)

        # NOTE: This blocks all other requests?
        cls.mpv.play(info["url"])
        cls._set_volume()

        # unset user selected flag
        # has to be after mpv.play b/c _mpv_eof will be called
        #  after mpv.play
        with cls.lock:
            cls.user_selected_flag = False

        return True

    @classmethod
    def playpause_handler(cls):
        cls._set_paused(not cls.mpv.pause.val)
        return True

    @classmethod
    def _set_paused(cls, state):
        cls.mpv.pause = state
        broadcast(cls.mpv.pause.val, "paused")

    @classmethod
    def change_volume(cls, delta):
        new_vol = cls.volume + delta
        if new_vol > 100.0 or new_vol < 0.0:
            return False
        cls.volume = new_vol
        cls._set_volume()
        return True

    @classmethod
    def change_position(cls, delta):
        if cls.currently_playing is None:
            return False

        new_pos = cls.mpv.time_pos + delta
        if new_pos > cls.mpv.length:
            return False
        if new_pos < 0.0:
            # reset to beginning
            new_pos = 0.0
        cls.mpv.time_pos = new_pos
        return True

    @classmethod
    def moveup_handler(cls, sid):
        if sid > len(cls.playlist):
            return False
        # if sid is the first song, we can't move it up
        if sid > 0:
            cls.playlist[sid-1], cls.playlist[sid] = cls.playlist[sid], cls.playlist[sid-1]
            # if moving up currently_playing, we need to fix that
            if sid == cls.currently_playing:
                cls._set_current(sid-1)
            elif sid-1 == cls.currently_playing:
                cls._set_current(sid)

        cls._save_playlist()
            
        return True

    # this is needed to correctly set mpv volume
    @classmethod
    def _set_volume(cls):
        # don't set the volume if nothing is playing b/c
        # setting volume will not work
        if cls.currently_playing is None:
            return

        vol_set_flag = False
        start_time = time.time()
        # 5 seconds until termination
        while not vol_set_flag and (time.time() - start_time < 5):
            try:
                cls.mpv.volume = cls.volume
                vol_set_flag = True
            except:
                pass

class JukeboxWebWorker(WebSocket):
    def received_message(self, message):
        if message.is_binary:
            return

        try:
            msg = json.loads(str(message))
        except:
            return

        # make sure the given type is a mapping, i.e. dict
        if not isinstance(msg, dict):
            return

        if "cmd" not in msg or "rqid" not in msg:
            return

        # parse the incoming message
        cmd = msg["cmd"] + "_handler"
        if cmd not in dir(self):
            return

        # call the action handle
        thread = threading.Thread(target=self.run, args=(cmd, msg))
        thread.start()

    def run(self, cmd, msg):
        getattr(self, cmd)(msg)

    def fail(self, rqid):
        # it is possible for the client to terminate before
        # the server sends the response
        if not self.client_terminated:
            self.send(json.dumps({
                "rqid": rqid,
                "status": False,
                "type": "unicast"
            }))

    def success(self, rqid, payload=None):
        # it is possible for the client to terminate before
        # the server sends the response
        if not self.client_terminated:
            self.send(json.dumps({
                "rqid": rqid,
                "status": True,
                "type": "unicast",
                "payload": payload
            }))

    # Add song to playlist
    # {'cmd': 'add', 'uri': URI}
    def add_handler(self, msg):
        if "uri" in msg:
            if Jukebox.add_handler(msg["uri"]) is True:
                self.success(msg["rqid"])
                broadcast(Jukebox.playlist, "playlist")
                return
        self.fail(msg["rqid"])

    # remove song from playlist
    # {'cmd': 'remove', 'id': ID}
    def remove_handler(self, msg):
        if "id" in msg:
            if Jukebox.remove_handler(msg["id"]) is True:
                self.success(msg["rqid"])
                # TODO: possibly replace this with a general "state" update
                broadcast(Jukebox.playlist, "playlist")
                return
        self.fail(msg["rqid"])

    # play the given id
    # {'cmd': 'play', 'id': ID}
    def play_handler(self, msg):
        if "id" in msg:
            if Jukebox.play_handler(msg["id"]) is True:
                self.success(msg["rqid"])
                return
        self.fail(msg["rqid"])

    # sets the play/pause state
    # {'cmd': 'playpause'}
    def playpause_handler(self, msg):
        if Jukebox.playpause_handler() is True:
            self.success(msg["rqid"])
            return
        self.fail(msg["rqid"])

    # increases volume
    # {'cmd': 'volup'}
    def volup_handler(self, msg):
        if Jukebox.change_volume(+5) is True:
            self.success(msg["rqid"])
            broadcast(Jukebox.volume, "volume")
            return
        self.fail(msg["rqid"]) 

    # decreases volume
    # {'cmd': 'voldn'}
    def voldn_handler(self, msg):
        if Jukebox.change_volume(-5) is True:
            self.success(msg["rqid"])
            broadcast(Jukebox.volume, "volume")
            return
        self.fail(msg["rqid"]) 

    # move song up
    # {'cmd': 'moveup'}
    def moveup_handler(self, msg):
        if "id" in msg:
            if Jukebox.moveup_handler(msg["id"]) is True:
                self.success(msg["rqid"])
                broadcast(Jukebox.playlist, "playlist")
                return
        self.fail(msg["rqid"])

    # rewind 10 sec
    # {'cmd': 'rewind'}
    def rewind_handler(self, msg):
        if Jukebox.change_position(-10) is True:
            self.success(msg["rqid"])
            return
        self.fail(msg["rqid"])

    # forward 10 sec
    # {'cmd': 'fastforward'}
    def fastforward_handler(self, msg):
        if Jukebox.change_position(+10) is True:
            self.success(msg["rqid"])
            return
        self.fail(msg["rqid"])

    # getters
    def get_playlist_handler(self, msg):
        self.success(msg["rqid"], payload=Jukebox.playlist)

    def get_volume_handler(self, msg):
        self.success(msg["rqid"], payload=Jukebox.volume)

    def get_current_handler(self, msg):
        self.success(msg["rqid"], payload=Jukebox.currently_playing)

    def get_paused_handler(self, msg):
        self.success(msg["rqid"], payload=Jukebox.mpv.pause.val)

if __name__ == "__main__":
    if "--visible" in sys.argv:
        VISIBILITY = True
    if "--debug" in sys.argv:
        DEBUG = True
    Jukebox.start_server()
