# NZSL Phrase Builder

A small prototype that turns simple English phrases into a rough NZSL gloss, looks up signs on the NZSL Dictionary, and displays the sign videos in order.

## What it does

- Converts simple English to a rough gloss using editable rules.
- Uses the NZSL Dictionary autocomplete/search/sign pages.
- Extracts MP4 video URLs from sign pages and displays them in sequence.
- Gives dictionary links where automatic matching fails.

## What it does **not** do

- It is **not** a fluent NZSL translator.
- It does not handle facial expression, spatial grammar, classifiers, role shift, or natural NZSL syntax.
- It may choose the wrong sign for ambiguous English words.

## Install

```bash
python -m venv .venv
source .venv/bin/activate  # Mac/Linux
# .venv\Scripts\activate   # Windows PowerShell
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

Then open the local URL Streamlit gives you.

## Example

Input:

```text
hello I would like an ice cream please
```

Rough gloss:

```text
HELLO ME WANT ICE-CREAM PLEASE
```

## Customising

Open `app.py` and edit:

- `PHRASE_MAP` for multi-word phrases, e.g. `"ice cream": ["ice-cream"]`
- `WORD_MAP` for single-word substitutions
- `DROP_WORDS` for English filler words to skip

## Use respectfully

This tool requests pages from the public NZSL Dictionary. Keep use light, cache results where possible, and do not bulk-download videos unless you have checked the licence and permissions for your use case.
