/**
 * Created by Vance Miller on 12/6/2014.
 */

$(window).resize(function() {
    var $controls = $(".controls-container");
    var $playlist = $("ol#playlist");
    if ($(this).height() > 400) {
        if ($controls.css("float") == "left") {
            $controls.css("margin-top", $(this).height() / 2 - $controls.height());
        } else {
            $controls.css("margin-top", 0);
        }
        $playlist.css("height", $(this).height() - $playlist.offset().top - 60);
    }
});

$(window).resize();