import csv
import argparse
from datetime import datetime
from pathlib import Path

import extract_em_translations
import prepare_translations

SECRETS_FILE = 'secrets.json'
LANGUAGES_CSV_FILE = 'languages.csv'

parser = argparse.ArgumentParser(description="REDCap Multilingual migration")
parser.add_argument("-j", "--json-template", required=True, help="Path to a JSON file downloaded from the new REDCap project's Multi-Language Manager.")
parser.add_argument("-l", "--language", required=True, help="Language to translate REDCap fields to.")
parser.add_argument("-o", "--output-file", help="Path to a new JSON file that will contain translations from the old external module.")
parser.add_argument("-q", "--escaped-quotes", action="store_true", help="If provided, suppresses default behavior of replace escaped double quote characters (\\\") with single quote characters (')")

################################################################
################################################################

def load_languages(csv_path, english_to_native: bool = False, english_to_shortcode: bool = False) -> dict:
    result = dict()
    with open(csv_path, 'r', encoding='utf-8-sig') as language_csv:
        w = csv.reader(language_csv)
        for row in w:
            if english_to_native:
                result[row[0]] = row[2]
            elif english_to_shortcode:
                result[row[0]] = row[1]
    return result

def validate_language(l: str, languages_to_shortcodes: dict) -> str:
    result = l
    if len(result) > 2:
        result = l.title()
    elif len(result) == 2:
        result = l.lower()
    
    actual_supported_languages = [k for k in languages_to_shortcodes.keys()] + [v for v in languages_to_shortcodes.values()]
    if result not in actual_supported_languages:
        raise ValueError(f"Unknown language '{result}'; language must be one of:\n\t{actual_supported_languages}")

    return result

def get_cmd_line_inputs(inp: argparse.Namespace) -> tuple[str, str, str, str, bool]:
    if not inp.json_template.endswith('.json'):
        raise ValueError(f"REDCap Multi Language Management file must have '.json' extension: {inp.json_template}")
    
    language = validate_language(inp.language, load_languages(LANGUAGES_CSV_FILE, english_to_shortcode=True))

    script_start_time = datetime.now().strftime('%Y%m%d_%H%M%S')
    translations_file = f"./output/{script_start_time}-translations.csv"
    if not inp.output_file:
        filled_json_output_file = f"./output/{script_start_time}-{language.lower()}-output.json"
        print(f"No output file specified; will use default: '{filled_json_output_file}'")
    else:
        filled_json_output_file = inp.output_file

    if Path(inp.json_template) == Path(filled_json_output_file):
        raise ValueError(f"Input .json file and output file must be different: {inp.json_template}")

    return (inp.json_template,
            language,
            translations_file,
            filled_json_output_file,
            not inp.escaped_quotes)

################################################################
################################################################

if __name__ == '__main__':
    redcap_mlm_template_json, language, translations_file, filled_json_output_file, replace_single_quotes_from_em_translations = get_cmd_line_inputs(parser.parse_args())

    # First, create the monolithic translations file to extract translations
    # from an old REDCap project's Multilingual external module
    print("(1/2) Extracting translations from old REDCap project....")
    extract_em_translations.create_translations_file(SECRETS_FILE, translations_file,
                                                     load_languages(LANGUAGES_CSV_FILE, english_to_native=True))
    print()
    # Next, fill out a template JSON file from a new REDCap project's Multi Language Manager
    # with translations from the translations file
    print("(2/2) Populating new REDCap project's MLM JSON with translations....")
    prepare_translations.fill_new_translation_json(translations_file, redcap_mlm_template_json, language,
                                                   load_languages(LANGUAGES_CSV_FILE, english_to_shortcode=True),
                                                   replace_single_quotes_from_em_translations, filled_json_output_file)
    print("Done!")
