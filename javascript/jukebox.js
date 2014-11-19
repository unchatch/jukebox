function playPause() {
	sendMsg({'cmd':'playpause'}, function() {

	}, function () {
		alert("Failed to play/pause");
	});
	if ($("#playpause").html() == "Play") {
		$("#playpause").html("Pause");
	} else {
		$("#playpause").html("Play");
	}
}

function play(id) {
	sendMsg({'cmd':'play', 'id':id}, function() {}, function(e) {
		alert("Failed to play video");
	});
}

function addVideo(youtubeURL) {
	sendMsg({'cmd':'add', 'uri': youtubeURL}, function(e) {

	}, function(e) {
		alert("Failed to add video");
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

function guiUpdatePlaylist(playlist) {
	console.log("PLAYLIST: ", playlist);
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
						console.log("VOLUME: ", resp);
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
		sendMsg({"cmd":"playlist"}, function(e){console.log(e);}, function(e){console.log(e);});
	};
});
