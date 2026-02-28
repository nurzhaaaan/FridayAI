def handle_command(text):
    text = text.lower()
    if "ескертпе" in text:
        return "Сізге ескертпе орнатылды!"
    elif "музыка" in text:
        return "Музыка ойнатылады 🎵"
    else:
        return None
