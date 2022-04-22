#!/usr/bin/env python
import requests
import csv
import json 
from pathlib import Path

################################################################
################################################################

def load_secrets(secrets_file_path: str) -> tuple[str, str]:
    '''Returns a 2-tuple of sensitive data located in secrets_file_path: ('api_token', 'url').
    Raises a ValueError if either field in secrets file is empty.
    '''
    result = dict()
    with open(secrets_file_path, "r") as f:
        result = json.load(f)
    if result['old_proj_api_token'] and result['old_proj_url']:
        return (result['old_proj_api_token'], result['old_proj_url'])
    raise ValueError(f"Failed to load {secrets_file_path} - did you fill in your REDCap project's API key and URL?")

def _request_metadata(token: str, url: str, check_cert: bool) -> str:
    '''Makes a REDCap API call for a REDCap project's metadata.
    Returns the text of the API response.
    Skips certificate checking if 'check_cert' is False.
    '''
    metadata_request = {
        'token': token,
        'content': 'metadata',
        'format': 'json'
    }
    r = requests.post(url, data=metadata_request, verify=check_cert)
    #print('>>> Metadata request HTTP Status: ' + str(r.status_code))
    return r.text

def get_metadata(token: str, url: str, check_cert: bool) -> list[dict]:
    '''Returns a list of dictionaries that contain metadata for a REDCap project's fields.
    '''
    if not check_cert:
        print("* Certificate checking is disabled.")
    raw_metadata_string = _request_metadata(token, url, check_cert)
    md = json.loads(raw_metadata_string)
    if type(md) == dict and md['error']:
        print(f"REDCap API returned an error while fetching metadata: {md['error']}")
        exit(1)
    return md

def transform_multi_choice_translations(t: dict) -> dict:
    '''Transforms a dict of translations for multiple-choice answers from this:
        {'0':
            {'English': 'No',
            'Español': 'No',
            '中文': '否',
            '한국어': '아니오',
            'Tiếng Việt': 'Không Đồng Ý'},
        '1':
            {'English': 'Yes',
            'Español': 'Sí',
            '中文': '是',
            '한국어': '예',
            'Tiếng Việt': 'Đồng Ý'}}
    to this:
        {'English': {'0': 'No', '1': 'Yes'},
        'Español': {'0': 'No', '1': 'Sí'},
        '中文': {'0': '否', '1': '是'},
        '한국어': {'0': '아니오', '1': '예'},
        'Tiếng Việt': {'0': 'Không Đồng Ý', '1': 'Đồng Ý'}}
    '''
    result = dict()
    for lang in t:
        for answer_choice in t[lang]:
            if answer_choice not in result:
                result[answer_choice] = dict()
            result[answer_choice][lang] = t[lang][answer_choice]
    return result

def write_translation_row(name: str, annot: str, w: csv.writer, languages_dict: dict) -> int:
    '''Parses a REDCap field for translations and writes at least one line to an output file.
    Returns the number of lines written for this particular field.
    '''
    #get current @p1000 name (lang, surveytext, errors, etc)
    start_of_p_field = annot.find("p1000")
    start_of_data = annot.find("{")

    #set up row to write to out file 
    if "p1000lang" in annot[start_of_p_field:start_of_data] or "p1000surveytext" in annot[start_of_p_field:start_of_data]:
        line_to_write = [name]
    else:
        line_to_write = [name + "_" + annot[start_of_p_field:start_of_data]]

    #determine where current p1000 field ends
    next_p_field = annot[start_of_data:].find("@p1000")
    if next_p_field > 0:
        end_of_data = next_p_field + start_of_data
    else:
        end_of_data = annot.rfind("}")+1

    #parse data
    to_parse = annot[start_of_data:end_of_data]
    translation_dict = json.loads(to_parse, strict = False)

    #write to out file
    lines_written = 0

    for lang in languages_dict.keys():
        try:
            line_to_write.append(translation_dict[languages_dict[lang]])
        except KeyError:
            line_to_write.append('')

    if "p1000answers" in annot[start_of_p_field:start_of_data]:
        # Write multiple-choice answers on separate lines
        # Should immediately follow the REDCap variable for their question prompt
        # Answers are stored in an embedded dict; parse that dict and write each answer on its own line
        if all(type(translation_dict[languages_dict[lang]]) == dict for lang in languages_dict.keys()):
            answers_dict = transform_multi_choice_translations(translation_dict)
            for answer_raw_value in answers_dict:
                # Initialize row with "multi_choice_question_variable[value=#]""
                answers_row = [name + "[value=" + answer_raw_value + "]"]
                for l in languages_dict.values():
                    # Answer translations are organized by their respective languages
                    # ("中文" instead of "Chinese", for example)
                    if l in answers_dict[answer_raw_value]:
                        answers_row.append(answers_dict[answer_raw_value][l])
                    else:
                        answers_row.append("")
                w.writerow(answers_row)
                lines_written += 1
    else:
        # Issue with CSV writer type annotations: https://stackoverflow.com/q/51264355
        # CSV writer is implemented in C, not in Python, so the writer's type is unavailable.
        # *Technically* nothing is broken, so... not going to worry about it too much :^)
        # Could fix by importing _csv instead of csv, but that's not great practice:
        #   https://til.codeinthehole.com/posts/how-to-typecheck-csv-objects-in-python/
        #   https://stackoverflow.com/a/12959997
        w.writerow(line_to_write)
        lines_written += 1

    #write next row if there is another p1000 field
    if next_p_field > 0:
        next_p_field = next_p_field + start_of_data
        lines_written += write_translation_row(name, annot[next_p_field:], w, languages_dict)

    return lines_written

def write_translations_file(output_path: str, languages_dict: dict[str:str], md: list[dict]) -> int:
    '''Iterate through each field in the old REDCap project's metadata `md` and
    write translations to `output_path` as a CSV file.
    Returns the number of lines written across the entire CSV file.
    '''
    output_parent_dir = Path(output_path).parent
    if not output_parent_dir.exists():
        output_parent_dir.mkdir()
        print(f"* Created directory: {output_parent_dir}")
    
    lines_written = 0

    with open(output_path, 'w',  newline='', encoding='utf-8-sig') as out_file:
        csv_header_row = ["Field"] + [k for k in languages_dict.keys()]
        csv_writer = csv.writer(out_file)
        csv_writer.writerow(csv_header_row)
        for field in md:
            field_name = field["field_name"]
            field_annotation = field["field_annotation"]
            # print(f"FIELD NAME ({type(field_name)}): {field_name}\n\tFIELD ANNOTATION ({type(field_annotation)}): {field_annotation}")
            if "@p1000" in field_annotation:
                lines_written += write_translation_row(field_name, field_annotation, csv_writer, languages_dict)
    return lines_written

def create_translations_file(secrets_path: str,
                             output_path: str,
                             supported_languages_dict: dict[str:str],
                             check_certificate: bool) -> None:
    # supported_languages_dict = {'language_in_english':'language_in_native_language'} (example: {'Spanish':'Español'})

    API_TOKEN,API_URL = load_secrets(secrets_path)
    print(f"Loaded secrets file: {secrets_path}")

    old_proj_metadata = get_metadata(API_TOKEN, API_URL, check_certificate)
    print("Got old REDCap project metadata")

    num_lines_written = write_translations_file(output_path, supported_languages_dict, old_proj_metadata)
    
    print(f"Wrote {num_lines_written} translated REDCap fields to: {output_path}")
    return
