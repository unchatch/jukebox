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

function submitVideo() {
	alert(document.forms["addVideo"]["videoUrl"].value);
	return false;

}

function addVideo(youtubeURL) {
	sendMsg({'cmd':'play', 'uri': youtubeURL}, function(e) {

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