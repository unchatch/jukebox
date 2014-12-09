/**
 * This function adds a video to the playlist.
 * @param youtubeURL The video to add
 */
function addVideo(youtubeURL) {
    $("#videoUrl").prop("disabled", true);
	$("#addVideo").prop("disabled", true);
    sendMsg({'cmd': 'add', 'uri': youtubeURL}, function (e) {
        $("#videoUrl").prop("disabled", false);
		$("#addVideo").prop("disabled", false);
        $("#videoUrl").val("");
    }, function (e) {
        alert("Failed to add video");
        $("#videoUrl").prop("disabled", false);
		$("#addVideo").prop("disabled", false);
        $("#videoUrl").val("");
    });
}

/**
 * This function should either fast forward or play the next video in the playlist...
 */
function fastforward() {
    sendMsg({'cmd': 'fastforward'}, function() {
        // success
    }, function() {
        // failure
        alert("Fast forward is not supported");
    });
}

/**
 * This function moves a video up one slot in the playlist. Primitive sorting.
 * @param id The video to move up
 */
function moveUp(id) {
    var $button = $("#moveup" + id);
    $button.prop("disabled", true);
    sendMsg({'cmd': 'moveup', 'id': id}, function() {
        // success
        var $li = $button.parent();
        $li.insertAfter($li.prev().prev());
    }, function() {
        // failure
    });
    $button.prop("disabled", false);

}
/**
 * This function plays a specified video.
 * @param id The video
 */
function play(id) {
    $("#play" + id).text("loading");
    $("#play" + id).prop("disabled", true);
    sendMsg({'cmd': 'play', 'id': id}, function () {
        // success
    }, function (e) {
        // failure
        alert("Failed to play video");
        $("#play" + id).prop("disabled", false);
        $("#play" + id).text("play");
    });
}

/**
 * This function toggles the play/pause state of the jukebox.
 */
function playPause() {
    sendMsg({'cmd': 'playpause'}, function () {
        // success
    }, function () {
        // failure
        alert("Failed to play/pause");
    });
}

/**
 * This function removes a video from the playlist.
 * @param id The video to remove
 */
function remove(id) {
    $('#remove' + id).prop("disabled", true);
	console.log(id)
    sendMsg({'cmd': 'remove', 'id': id}, function (e) {
        // success
        console.log("successfully removed " + id);
    }, function (e) {
        // failure
        alert("Failed to remove video");
        $('#remove' + id).prop("disabled", false);
    });
}

/**
 * This function should either rewind or play the previous video in the playlist...
 */
function rewind() {
    sendMsg({'cmd': 'rewind'}, function() {
        // success
    }, function() {
        // failure
        alert("Rewind is not supported");
    });
}

/**
 * This function increases the volume.
 */
function volUp() {
    sendMsg({'cmd': 'volup'}, function (e) {
        // success
    }, function (e) {
        // failure; ignore
    });
}

/**
 * This function decreases the volume.
 */
function volDown() {
    sendMsg({'cmd': 'voldn'}, function (e) {
        // success
    }, function (e) {
        // failure; ignore
    });
}

////// GUI update functions
/**
 * This function toggles the play pause button. It is called by the websocket's onmessage function.
 */
function guiTogglePlayPause(state) {
	var disabled = currently_playing == null;
    if (state) {
        $("#playpause").html("Play").prop("disabled", disabled);
    } else {
        $("#playpause").html("Pause").prop("disabled", disabled);
    }
}

/**
 * Update the HTML backing the playlist. Called by the websocket's onmessage function.
 * @param playlist the playlist.
 */
function guiUpdatePlaylist(playlist) {
    var $playlist = $("#playlist");
    $playlist.empty();
    var list = [];
    playlist.forEach(function (elm, idx, arr) {
		console.log(elm);
        var li = document.createElement("li");
        li.className = "playlist_elm";
        li.id = idx + "_li";

        var button = document.createElement("button");
        button.id = "play" + idx;
        button.className = "play";
        button.textContent = "play";
        button.onclick = play.bind(null, idx);
        li.appendChild(button);

        var removeButton = document.createElement("button");
        removeButton.textContent = "remove";
        removeButton.id = "remove" + idx;
        removeButton.onclick = remove.bind(null, idx);
        li.appendChild(removeButton);

        var moveUpButton = document.createElement("button");
        moveUpButton.textContent = "move up";
        moveUpButton.id = "moveup" + idx;
        moveUpButton.onclick = moveUp.bind(null, idx);
        li.appendChild(moveUpButton);

        var link = document.createElement("a");
        link.href = elm.url;
        // wheeee no sanitization here
        link.textContent = elm.title;
        link.target = "_blank";
        li.appendChild(link);
        li.title = elm.title;

        list.push(li);
    });
    $playlist.append(list);

	// update currently playing
	guiUpdateCurrentlyPlaying(currently_playing);
}

/**
 * Update the volume GUI. Called by the websocket's onmessage function.
 * @param vol The new volume
 */
function guiUpdateVolume(vol) {
    $("#volume").text(vol + " %");
}

/**
 * Update the currently playing GUI. Called by the websocket's onmessage function.
 * @param current The currently playing song.
 */
var currently_playing = null;
function guiUpdateCurrentlyPlaying(current) {
	currently_playing = current;
    if (current == null) return;
    $(".playlist_elm > button.play").prop('disabled', false).text("play");
    var id = "#play" + current;
    $(id).text("playing");
    $(id).prop("disabled", true);
}

// websocket interface
var sendMsg;

$(document).ready(function () {
    if (!window.WebSocket) {
        alert("Do not have websockets! Boo you >:-(");
        return;
    }

    var ws = new WebSocket("ws://localhost:9000/rq");

    sendMsg = (function (ws) {
        var ws = ws;
        var rqid = 0;
        var wait = {};

        ws.onmessage = function (ev) {
            resp = JSON.parse(ev.data);
			console.log(resp);

            if (resp["type"] == "broadcast") {
				var payload = resp["payload"]
                switch (resp["label"]) {
                    case "playlist":
                        guiUpdatePlaylist(payload);
                        break;
                    case "volume":
                        guiUpdateVolume(payload);
                        break;
                    case "paused":
                        guiTogglePlayPause(payload);
                        guiUpdateCurrentlyPlaying(currently_playing);
                        break;
                    case "current":
                        guiUpdateCurrentlyPlaying(payload);
                        break;
                    default:
                        console.log("BAD BROADCAST: ", resp);
                }
                return;
            }

            if (wait[resp["rqid"]] === undefined) {
                console.log("BAD MESSAGE:", resp);
                console.log(resp);
            }
            else {
                if (resp["status"] == false) {
                    wait[resp["rqid"]]["failure"](wait[resp["rqid"]]["request"]);
                }
                else {
                    wait[resp["rqid"]]["success"](resp);
                }
            }
        };

        return function (jsonMsg, success_call, fail_call) {
            jsonMsg["rqid"] = rqid;
            wait[rqid] = {
                "request": jsonMsg,
                "success": success_call,
                "failure": fail_call
            };
            rqid++;
            ws.send(JSON.stringify(jsonMsg));
        };
    })(ws);


    ws.onopen = function (ev) {
        console.log("WS Ready");
        sendMsg({"cmd": "get_playlist"}, function (e) {
            guiUpdatePlaylist(e["payload"]);
        }, function (e) {
        });
        sendMsg({"cmd": "get_volume"}, function (e) {
            guiUpdateVolume(e["payload"]);
        }, function (e) {
        });
        sendMsg({"cmd": "get_current"}, function (e) {
            guiUpdateCurrentlyPlaying(e["payload"]);
        }, function (e) {
        });
        sendMsg({"cmd": "get_paused"}, function (e) {
			guiTogglePlayPause(e["payload"])
        }, function (e) {
        });
    };

    $("#addVideo").on("click", function () {
        addVideo($("#videoUrl").val());
    });
});
