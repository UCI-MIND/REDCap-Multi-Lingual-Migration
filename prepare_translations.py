import csv
import json

from pathlib import Path

################################################################
################################################################

class TranslatedField:
    '''Contains data for a single translated REDCap field (one line in the CSV).
    '''
    def __init__(self, field: str, csv_row: list[str], language_order_key: list[str]):
        # language_order_key: list of languages as they appear in the first row of the translations CSV
        # i.e. ['English', 'Spanish', ... ]

        # Size in memory could be further reduced by removing the TranslatedField.field_name attribute, but there
        # isn't a need for space optimization at the moment and the attribute helps with debugging.
        self.field_name: str                = field     # REDCap variable name
        self.translations: dict[str:str]    = dict()
        self.translated: bool               = False     # Has this translation been applied to the new JSON?
        self.is_incomplete: bool            = False     # Does this translation have any missing languages?
        for lang,text in zip(language_order_key, csv_row):
            self.translations[lang] = text
            # The CSV will have an empty cell if a given translation is missing
            if text == "":
                self.is_incomplete = True

    def __repr__(self):
        return f"TranslatedField(field_name={self.field_name},translations={str(self.translations)},translated={self.translated},is_incomplete={self.is_incomplete})"

    def get_translation(self, l: str, available_languages: dict, replace_quotes: bool = False) -> str:
        '''Returns a translation of this field in language `l` and sets this field's 'translated' flag to True.
        `l` may be either a 2-character shortcode or a language in English (i.e. "Spanish" or "es", not "Español").
        Will modify the translation slightly, replacing '___' substrings with '@' and may optionally
        replace escaped double quotes (\") with single quotes.
        '''
        # This class stores languages according their original name, so:
        #       self.translations['Spanish']    # (returns a string)
        #       self.translations['es']         # KeyError
        # Need the `available_languages` dict to allow lookups via shortcode.
        t: str = self.translations[available_languages[l]] if l not in self.translations else self.translations[l]

        # REDCap appears to replace '@' chars with '___' in field data, breaking email addresses.
        t = t.replace('___', '@')

        # JSON files use double quotes by design, so any quotes in JSON values need to be escaped, and
        # the characters \" appear in values where only double quotes should appear.
        # REDCap doesn't properly parse these escaped quotes, so any double quotes used in, for example,
        # HTML styling ( <div style="background-color: #e6ffff;" ) would not render properly (if at all).
        if replace_quotes:
            t = t.replace('"', "'")
        
        self.translated = True
        return t.strip()

################################################################
################################################################

def load_csv(csv_path: str) -> dict[TranslatedField]:
    result: dict[TranslatedField] = dict()
    # A bit of redudancy: result['example_field_name'] is a TranslatedField object, so this silliness is valid:
    #   result['example_field_name'].field_name == 'example_field_name'     # True

    with open(csv_path, "r", encoding='utf-8-sig') as csv_file:
        current_line = 0
        expected_row_length = 0
        detected_languages = []
        
        translations_reader = csv.reader(csv_file, delimiter=',')
        for row in translations_reader:
            current_line += 1
            if current_line == 1:
                # Detect some initial info from the first line in the CSV
                expected_row_length = len(row)
                detected_languages = row[1:]
                ###print(f"* Found {expected_row_length-1} language(s): {', '.join(detected_languages)}")
                continue
            if len(row) == expected_row_length:
                result[row[0]] = TranslatedField(row[0], row[1:], detected_languages)
            else:
                problematic_variable = ""
                if len(row) > 0:
                    problematic_variable += "(Field: '" + row[0] + "') "
                print(f"*** Missing {row.count('')} translation(s) at line {current_line} {problematic_variable}(skipping)")

    return result

def load_json(json_path: str) -> dict:
    result = dict()
    with open(json_path, encoding='utf-8-sig') as json_file:
        result = json.load(json_file)
    return result

def apply_translations(translations: list[TranslatedField],
                       original_json: dict,
                       desired_language: str,
                       available_languages: dict,
                       replace_quotes: bool = False) -> int:
    '''Populates empty translation fields in `original_json` with translations to `desired_language`.
    Returns the number of translations applied.
    '''
    successful_translations: list[int] = []

    for category in original_json:
        if type(original_json[category]) == list and len(original_json[category]) > 0:
            ###print(f"* Applying translations to REDCap category '{category}'...")
            this_categorys_successful_translations = 0
            redcap_fields_missing_translations = []
            for text_string_index in range(len(original_json[category])):
                this_redcap_field = original_json[category][text_string_index]
                # Records in the original JSON categories can look like this:
                #
                # { "id": "THE_ID_ALSO_IN_THE_CSV",
                #   "translation": "TRANSLATION_GOES_HERE"
                # }
                #
                # or this (multiple choice answers have translations in the 'enum' field):
                #
                # { "id": "THE_ID_ALSO_IN_THE_CSV",
                #   "form": "blahblah",
                #   "label": {
                #       "hash": "blahblah",
                #       "translation": "TRANSLATION_GOES_HERE"
                #    },
                #    "enum": [
                #       { "id": 0,
                #         "hash": "blahblah",
                #         "translation": "MULTIPLE_CHOICE_TRANSLATIONS_GO_HERE"
                #       }, ...
                #    ]
                # }
                if 'id' in this_redcap_field:
                    field_name = this_redcap_field['id']
                    if field_name in translations:
                        if 'translation' in this_redcap_field and this_redcap_field['translation'] == '':
                            #print(f"Field name: {field_name} | {this_redcap_field}")
                            this_redcap_field['translation'] = translations[field_name].get_translation(desired_language, available_languages, replace_quotes)
                            this_categorys_successful_translations += 1
                        
                        elif 'label' in this_redcap_field and \
                        type(this_redcap_field['label']) == dict and \
                        'translation' in this_redcap_field['label'] and \
                        this_redcap_field['label']['translation'] == '':
                            #print(f"Field name (translation in 'label'): {field_name} | {this_redcap_field}")
                            this_redcap_field['label']['translation'] = translations[field_name].get_translation(desired_language, available_languages, replace_quotes)
                            this_categorys_successful_translations += 1
                        
                        if 'enum' in this_redcap_field and \
                        type(this_redcap_field['enum']) == list:
                            # Apply multiple-choice translations
                            #print(f"Field name (multiple choices in 'enum'): {field_name} | via {this_redcap_field}")
                            multiple_choice_answers_list = this_redcap_field['enum']
                            for answer_index in range(len(multiple_choice_answers_list)):
                                if multiple_choice_answers_list[answer_index]['translation'] == '':
                                    csv_entry = this_redcap_field['id'] + "[value=" + str(multiple_choice_answers_list[answer_index]['id']) + "]"
                                    if csv_entry in translations:
                                        this_redcap_field['enum'][answer_index]['translation'] = translations[csv_entry].get_translation(desired_language, available_languages, replace_quotes)
                                        this_categorys_successful_translations += 1
                        
                        if 'note' in this_redcap_field and \
                        'translation' in this_redcap_field['note'] and \
                        this_redcap_field['note']['translation'] == '':
                            # Apply field note translations
                            csv_entry = field_name + "_p1000notes"
                            if csv_entry in translations:
                                # print(f"* {field_name} - field note in CSV: {csv_entry} | via {this_redcap_field}")
                                this_redcap_field['note']['translation'] = translations[csv_entry].get_translation(desired_language, available_languages, replace_quotes)
                                this_categorys_successful_translations += 1
                    else:
                        # Found a REDCap field with no corresponding translation in the CSV
                        redcap_fields_missing_translations.append(field_name)
                else:
                    # All REDCap fields in the JSON should have an 'id' field; otherwise, JSON has probably been tampered with
                    print("[REDCap MLM template JSON] Found REDCap field without an 'id': " + str(this_redcap_field))
            successful_translations.append(this_categorys_successful_translations)
            #print(f"{category} missing translations for these fields: {redcap_fields_missing_translations}")
    return sum(successful_translations)

def write_new_json_file(filled_json: dict, new_json_file: str) -> None:
    output_parent_dir = Path(new_json_file).parent
    if not output_parent_dir.exists():
        output_parent_dir.mkdir()
        print(f"* Created directory: {output_parent_dir}")

    with open(new_json_file, "w+", encoding='utf-8-sig') as outfile:
        json.dump(filled_json, outfile, ensure_ascii=False, indent=2)
    return

def fill_new_translation_json(em_translations_csv_path: str,
                              redcap_mlm_empty_json_path: str,
                              selected_language: str,
                              supported_languages_dict: dict,
                              replace_quotes: bool,
                              final_json_path: str) -> None:
    # supported_languages_dict = {'language_in_english':'2-char_shortcode'} (or vice-versa; example: {'Spanish':'es'})
    # Add a reverse mapping to support accepting either full language names *or* shortcodes as valid user input
    supported_languages_dict |= dict((supported_languages_dict[i], i) for i in supported_languages_dict)

    translations: dict[TranslatedField] = load_csv(em_translations_csv_path)
    print("Loaded translations")

    loaded_json_template = load_json(redcap_mlm_empty_json_path)
    print(f"Loaded template JSON file: {redcap_mlm_empty_json_path}")

    num_tls = apply_translations(translations, loaded_json_template, selected_language, supported_languages_dict, replace_quotes)

    # Might be helpful for debugging:
    #print(f"Fields with incomplete translations: {[translations[t].field_name for t in translations if translations[t].is_incomplete]}")
    #print(f"Translated fields left untouched:    {[translations[t].field_name for t in translations if not translations[t].translated]}")

    write_new_json_file(loaded_json_template, final_json_path)
    print(f"Wrote {num_tls} translations to: {final_json_path}")
    return
