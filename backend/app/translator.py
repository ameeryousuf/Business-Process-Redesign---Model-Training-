import argostranslate.translate

_installed_languages = argostranslate.translate.get_installed_languages()
_de_lang = next((l for l in _installed_languages if l.code == "de"), None)
_en_lang = next((l for l in _installed_languages if l.code == "en"), None)

if _de_lang and _en_lang:
    _translation = _de_lang.get_translation(_en_lang)
else:
    _translation = None


def _translate_one(name):
    if _translation is None:
        return name
    try:
        return _translation.translate(name)
    except Exception:
        return name


def translate_names(parsed):
    all_items = []
    all_items.extend(parsed.tasks)
    all_items.extend(parsed.gateways)
    all_items.extend(parsed.start_events)
    all_items.extend(parsed.end_events)

    names_to_translate = []
    for item in all_items:
        name = item.get("name")
        if name and name.strip():
            names_to_translate.append(name)

    if not names_to_translate:
        return parsed

    unique_names = list(set(names_to_translate))
    translation_map = {name: _translate_one(name) for name in unique_names}

    for item in all_items:
        original_name = item.get("name")
        if original_name and original_name in translation_map:
            item["name"] = translation_map[original_name]

    return parsed


if __name__ == "__main__":
    from app.bpmn_parser import parse_bpmn

    parsed = parse_bpmn("data/training_processes/process_0000.bpmn")

    print("Before translation:")
    for t in parsed.tasks:
        print(" ", t["name"])

    parsed = translate_names(parsed)

    print("\nAfter translation:")
    for t in parsed.tasks:
        print(" ", t["name"])