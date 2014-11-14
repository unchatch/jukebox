function playPause(success, fail) {
	sendMsg({'cmd':'playpause'}, success, fail);
	if ($("#playpause").html().equals("Play")) {
		$("#playpause").html("Pause");
	} else {
		$("#playpause").html("Play");
	}
}

function addVideo(youtubeURL, success, fail) {
	sendMsg({'cmd':'play', 'uri': youtubeURL}, success, fail);
}

function volUp() {
	sendMsg({'cmd':'volup'});
}

function volDown() {
	sendMsg({'cmd':'voldn'});
}


//////

var sendMsg;

function guiUpdatePlaylist(resp) {
	var playlist = resp["playlist"];
	console.log(playlist);
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
			if (resp["playlist"] !== undefined) {
				guiUpdatePlaylist(resp);
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
		sendMsg({"cmd":"playlist"});
	};
});