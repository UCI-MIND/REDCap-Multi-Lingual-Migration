# REDCap Multi-Lingual Migration
Automates much of the process of moving translations from the [old Multilingual external module](https://github.com/smartinkc/Multilingual) to the newer built-in Multi-Language Management (MLM) page.

Developed and tested with Python 3.9.10, although this should work with all versions of **Python >= 3.9**.

Functionality of this script is split into 2 parts:
* `extract_em_translations.py` makes a REDCap API call to the old project to obtain its entire collection of translations from the old Multilingual external module. Stores translations in a timestamped .csv file in `output/`, which is generated automatically.
* `prepare_translations.py` uses this .csv file to provide translations to a .json file from the new REDCap project's MLM page. This creates another .json file that can be re-imported into the new REDCap project's MLM with all applicable translations pre-filled.

Please note the license terms in `LICENSE.txt` - this tool is not guaranteed to be compatible with your own REDCap projects "out of the box"; some tinkering may be required. UCI MIND lacks the resources to maintain or add features to this tool, although we may push critical updates as necessary.

# Before use
* Edit `secrets.json` and add the API token and URL from your old REDCap project - the one with the Multilingual external module. Visit that project's "API" and "API Playground" pages for details.
* Edit `languages.csv` and add the languages that your REDCap projects support.
  * Column 1 should contain the language in English, column 2 should contain a two-character shortcode for the language, and column 3 should contain the language in its native language (example: _Spanish_, _es_, _Español_)
* Ensure that the new REDCap project **uses the exact same variable names** as the old REDCap project.
* Download template .json files for each language on your new REDCap project's Multi-Language Management page:
  * Multi-Language Management -> Actions -> "Export Language" (the blue file with a downwards arrow) -> Select "JSON" under "Export Options" -> "Download Language"
  * A folder named `multi_language_manager_json/` has been included as a place to put these files, as well as a basic JSON file that roughly follows the format the scripts expect.
* When running this script, it is recommended to create a virtual environment to keep packages isolated on your system:
```
cd {into this repository's folder}

# Create a Python virtual environment (only need to do this once):
python -m venv .venv

# Activate the virtual environment:
.\.venv\Scripts\Activate.ps1
# No file extension needed on other platforms
# Windows: .ps1 for PowerShell or .bat for Command Prompt

# If using PowerShell and "running scripts is disabled on this system", need to
# enable running external scripts. Open PowerShell as admin and use this command:
#     set-executionpolicy remotesigned
# (only need to do this once)

# While in the virtual env, install packages (only need to do this once):
python -m pip install -r requirements.txt

# Run the script, develop, debug, etc.:
python main.py {arguments, see below} ...

# Deactivate when done
deactivate
```

# Usage
Use on a command line (brackets indicate optional arguments):
```
python main.py [-h] -j JSON_TEMPLATE -l LANGUAGE [-o OUTPUT_FILE] [-q] [--no-check-certificate]
```

Arguments:
| Argument | Shorthand | Required? | Description |
| :------: | :-------: | :-------: | :---------- |
| `--help` | `-h` |  | Display a help message and exit. |
| `--json-template` | `-j` | ✅ | Path to a .json file downloaded from a new REDCap project's Multi-Language Management system. Configure this in tandem with `--language`. |
| `--language` | `-l` | ✅ | Determines which language to translate REDCap fields to. Can be a two-character shortcode or a full name (i.e. 'es' or 'Spanish' are valid). Configure this in tandem with `--json-template`. |
| `--output-file` | `-o` |  | Destination file of the filled-out template .json. If this argument is absent, the new .json file will be written to `output/` with a timestamped file name. |
| `--escaped-double-quotes` | `-q` |  | If this argument is provided, backslash characters are prepended to double quote characters (`\"`) in the final JSON translations file. If this argument is absent, double quote characters will be replaced with single quote characters (`'`). |
| `--no-check-certificate` |  |  | If this argument is provided, certificate checking is disabled during the initial API request for translations from the older REDCap project. |

To import your filled-in JSON files to your new REDCap project:
* Multi-Language Management -> Actions -> "Edit Language" (the pencil icon) -> "Import from file or system" -> "Browse" and select your filled-in .json file -> check "use imported values" -> "Import"

After importing, it is highly recommended to perform a manual check of the translations to ensure that no fields were missed or translated incorrectly. Be vigilant for any non-functioning HTML or JSON-esque code fragments.
