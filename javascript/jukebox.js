function playPause() {
	sendMsg({'cmd':'playpause'}, function() {
	}, function () {
		alert("Failed to play/pause");
	});
}

function guiTogglePlayPause() {
	if ($("#playpause").html() == "Play") {
		$("#playpause").html("Pause");
	} else {
		$("#playpause").html("Play");
	}
}

function play(id) {
	$("#" + id).text("loading");
	$("#" + id).prop("disabled", true);
	sendMsg({'cmd':'play', 'id':id}, function() {}, function(e) {
		alert("Failed to play video");
		$("#" + id).prop("disabled", false);
	$("#" + id).text("play");
	});
}

function addVideo(youtubeURL) {
	$("#videoUrl").prop("disabled", true);
	sendMsg({'cmd':'add', 'uri': youtubeURL}, function(e) {
		$("#videoUrl").prop("disabled", false);
		$("#videoUrl").val("");
	}, function(e) {
		alert("Failed to add video");
		$("#videoUrl").prop("disabled", false);
		$("#videoUrl").val("");
	});
}

function volUp() {
	sendMsg({'cmd':'volup'}, function(e) {
	}, function(e) {
		alert("Failed to increase volume");
	});
}

function volDown() {
	sendMsg({'cmd':'voldn'}, function(e) {
	}, function(e) {
		alert("Failed to decrease volume");
	});
}


//////

var sendMsg;

function playlistPlay(ev) {
	play(ev.toElement.id);
}

function guiUpdatePlaylist(playlist) {
	$("#playlist").empty();
	var lis = [];
	playlist.forEach(function(elm, idx, arr) {
		var li = document.createElement("li");
		li.className = "playlist_elm";

		var button = document.createElement("button");
		button.id = elm.id;
		button.textContent = "play";
		button.onclick = playlistPlay;
		li.appendChild(button);

		var link = document.createElement("a");
		link.href = elm.uri;
		// wheeee no sanitization here
		link.textContent = elm.title;
		link.target = "_blank";
		li.appendChild(link);

		lis.push(li);
	});

	$("#playlist").append(lis);
}

function guiUpdateVolume(vol) {
	$("#volume").text(vol + " %");
}

function guiUpdateCurrentlyPlaying(current) {
	if (current["current"] == null) return;
	$(".playlist_elm > button").prop('disabled',false).text("play");
	var id = "#" + current["current"];
	$(id).text("playing");
	$(id).prop("disabled", true);
}

function generalFail(req) {
	console.log("GENERAL FAIL ON REQUEST:", req);
}

$(document).ready(function() {
	if (!window.WebSocket) {
		alert("Do not have websockets! Boo you >:-(");
		return;
	}

	var ws = new WebSocket("ws://localhost:9000/rq");

	sendMsg = (function(ws) {
		var ws = ws;
		var rqid = 0;
		var wait = {};

		ws.onmessage = function(ev) {
			resp = JSON.parse(ev.data);
			if (resp["broadcast"] === true) {
				switch(resp["type"]) {
					case "playlist":
						guiUpdatePlaylist(resp["playlist"]);
						break;
					case "volume":
						guiUpdateVolume(resp["value"]);
						break;
					case "playpause":
						guiTogglePlayPause();
						break;
					case "current":
						guiUpdateCurrentlyPlaying(resp);
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

		return function(jsonMsg, success_call, fail_call) {
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


	ws.onopen = function(ev) {
		console.log("WS Ready");
		sendMsg({"cmd":"playlist"}, function(e){guiUpdatePlaylist(e["playlist"]);}, function(e){});
		sendMsg({"cmd":"volume"}, function(e){guiUpdateVolume(e["volume"]);}, function(e){});
		sendMsg({"cmd":"current"}, function(e){guiUpdateCurrentlyPlaying(e);}, function(e){});
		sendMsg({"cmd":"ispaused"}, function(e){
			$("#playpause").html(e.ispaused ? "Play" : "Pause");
		},function(e){});
	};

	$("#addVideo").on("click", function() {
		addVideo($("#videoUrl").val());
	});
});
