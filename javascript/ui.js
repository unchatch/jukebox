/**
 * Created by Vance Miller on 12/6/2014.
 */

$(window).resize(function() {
    if ($(this).height() > 400) {
        $("ol#playlist").css("height", $(this).height() - $("ol#playlist").offset().top - 60);

        if ($(".controls-container").css("float") == "left") {
            $(".controls-container").css("margin-top", $(this).height() / 2 - $(".controls-container").height());
        }

    }
    });

$(window).resize();