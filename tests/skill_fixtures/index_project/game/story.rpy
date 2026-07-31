define duke = Character("Duke", what_font="fonts/noble.ttf", who_color="#c8a96b")
define drifter = Character("Rowan")
define god = Character(None)

# duke "This commented-out line is not localization source evidence."

screen preferences_panel():
    text "Preferences"
    textbutton "Return" action Return()

label start:
    duke "You are late, [player_name]."
    drifter "Yeah, yeah. The road was a mess."
    "The hall fell silent."

    menu:
        "Tell him the truth.":
            jump tell_truth
        "Keep quiet.":
            jump stay_silent

    duke "I said {i}your{/i} name."
    extend " Do not make me repeat it.{w}"
    duke "He said, \"Wait.\"  Then he left."
    drifter 'Don\'t push it.'

    god "{font=fonts/divine.ttf}{color=#d8c8ff}YOU HAVE RETURNED.{/color}{/font}"

    python:
        debug_message = "This executable string must not be indexed."

    voice "audio/duke_warning.ogg"
    return
