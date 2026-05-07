"""
NZSL Phrase Builder

A small Streamlit prototype that turns simple English text into a rough NZSL gloss,
looks up signs from the NZSL Dictionary, and displays the sign videos in sequence.

Important: this is a learning aid, not a translator. NZSL has its own grammar,
facial expression, spatial grammar, classifiers, and context-dependent signs.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable
from urllib.parse import quote_plus, urljoin

import requests
import streamlit as st
from bs4 import BeautifulSoup

BASE_URL = "https://www.nzsl.nz"
HEADERS = {
    "User-Agent": "NZSLPhraseBuilder/0.1 (+personal learning prototype)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
REQUEST_PAUSE_SECONDS = 0.15  # keep requests gentle

# Common English words that usually should not be individually signed in a phrase builder.
DROP_WORDS = {
    "a", "an", "the", "to", "for", "of", "and", "or", "but", "is", "are", "am",
    "be", "being", "been", "do", "does", "did", "would", "could", "should", "can",
    "may", "might", "will", "just", "some", "one",
}

# Phrase-level replacements. Longer phrases are applied before individual words.
# Add your own mappings as you learn better NZSL phrasing.
PHRASE_MAP = {
    "i would like": ["me", "want"],
    "i'd like": ["me", "want"],
    "i want": ["me", "want"],
    "can i have": ["me", "want"],
    "could i have": ["me", "want"],
    "ice cream": ["ice-cream"],
    "thank you": ["thank-you"],
    "good morning": ["good-morning"],
    "good afternoon": ["good-afternoon"],
    "good night": ["good-night"],
    "my name is": ["my", "name"],
}

# Word-level replacements.
WORD_MAP = {
    "i": "me",
    "i'm": "me",
    "im": "me",
    "please": "please",
    "hello": "hello",
    "hi": "hello",
    "thanks": "thank-you",
    "thankyou": "thank-you",
}


@dataclass(frozen=True)
class SignResult:
    query: str
    gloss: str | None
    page_url: str | None
    video_url: str | None
    note: str = ""


def normalise_text(text: str) -> str:
    text = text.lower().strip()
    text = text.replace("’", "'")
    text = re.sub(r"[^a-z0-9'\-\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def english_to_rough_gloss(text: str) -> list[str]:
    """Very simple English -> rough NZSL gloss tokens."""
    text = normalise_text(text)
    tokens: list[str] = []

    # Greedy phrase matching from left to right.
    words = text.split()
    i = 0
    phrase_keys = sorted(PHRASE_MAP, key=lambda p: len(p.split()), reverse=True)
    while i < len(words):
        matched = False
        remaining = " ".join(words[i:])
        for phrase in phrase_keys:
            phrase_words = phrase.split()
            if remaining.startswith(phrase) and words[i:i + len(phrase_words)] == phrase_words:
                tokens.extend(PHRASE_MAP[phrase])
                i += len(phrase_words)
                matched = True
                break
        if matched:
            continue

        word = words[i]
        if word not in DROP_WORDS:
            tokens.append(WORD_MAP.get(word, word))
        i += 1

    # Remove adjacent duplicates while preserving order.
    cleaned: list[str] = []
    for token in tokens:
        if token and (not cleaned or cleaned[-1] != token):
            cleaned.append(token)
    return cleaned


def candidate_terms(term: str) -> list[str]:
    variants = [term, term.replace("-", " "), term.replace(" ", "-")]
    out: list[str] = []
    for v in variants:
        if v and v not in out:
            out.append(v)
    return out


@lru_cache(maxsize=512)
def autocomplete(term: str) -> list[str]:
    try:
        r = requests.get(
            f"{BASE_URL}/signs/autocomplete",
            params={"term": term},
            headers=HEADERS,
            timeout=12,
        )
        time.sleep(REQUEST_PAUSE_SECONDS)
        if r.ok:
            data = r.json()
            return [str(x) for x in data]
    except Exception:
        return []
    return []


@lru_cache(maxsize=512)
def fetch_first_sign(term: str) -> SignResult:
    """Find the first likely dictionary result and its main video."""
    for search_term in candidate_terms(term):
        # Autocomplete often gives canonical glosses; prefer exact-ish suggestions.
        suggestions = autocomplete(search_term)
        search_terms = []
        exact = [s for s in suggestions if s.lower() == search_term.lower()]
        search_terms.extend(exact or suggestions[:3] or [search_term])

        for s_term in search_terms:
            try:
                # IMPORTANT: nzsl.nz expects the keyword search parameter to be `s`, not `s[]`.
                # Using `s[]` can return the unfiltered/default search page, which makes every
                # token pick the same first result, e.g. “all of you”.
                r = requests.get(
                    f"{BASE_URL}/signs/search",
                    params={
                        "s": s_term,
                        "hs": "",
                        "l": "",
                        "lg": "",
                        "tag": "",
                        "usage": "",
                        "utf8": "✓",
                    },
                    headers=HEADERS,
                    timeout=12,
                )
                time.sleep(REQUEST_PAUSE_SECONDS)
                if not r.ok:
                    continue
                soup = BeautifulSoup(r.text, "html.parser")

                # Search results contain links to /signs/:id and often a video preview.
                sign_link = None
                for a in soup.select('a[href*="/signs/"]'):
                    href = a.get("href")
                    if href and re.search(r"/signs/\d+", href):
                        sign_link = urljoin(BASE_URL, href)
                        break
                if not sign_link:
                    continue

                # Open the sign page and extract the primary video source.
                page = requests.get(sign_link, headers=HEADERS, timeout=12)
                time.sleep(REQUEST_PAUSE_SECONDS)
                if not page.ok:
                    continue
                page_soup = BeautifulSoup(page.text, "html.parser")

                source = page_soup.select_one("video source[src], source[src]")
                video_url = urljoin(BASE_URL, source.get("src")) if source else None

                h1 = page_soup.select_one("h1")
                gloss = h1.get_text(strip=True) if h1 else s_term

                return SignResult(
                    query=term,
                    gloss=gloss,
                    page_url=sign_link,
                    video_url=video_url,
                )
            except Exception as e:
                last_error = str(e)
                continue

    return SignResult(
        query=term,
        gloss=None,
        page_url=f"{BASE_URL}/signs/search?s={quote_plus(term)}",
        video_url=None,
        note="No direct video found. Open the dictionary search link and choose the best sign manually.",
    )


def render_video(result: SignResult, index: int) -> None:
    title = result.gloss or result.query
    st.markdown(f"### {index}. {title}")
    if result.video_url:
        st.video(result.video_url)
    else:
        st.warning(result.note or "No video found automatically.")
    if result.page_url:
        st.markdown(f"[Open dictionary page/search]({result.page_url})")


def main() -> None:
    st.set_page_config(page_title="NZSL Phrase Builder", page_icon="🤟", layout="wide")
    st.title("NZSL Phrase Builder")
    st.caption("Text → rough NZSL gloss → NZSL Dictionary sign videos in sequence")

    st.info(
        "This is not a true NZSL translator. It strings together isolated dictionary signs. "
        "Use it for vocabulary practice, then check phrasing with NZSL learning resources or a fluent signer."
    )

    phrase = st.text_input(
        "English phrase",
        value="hello I would like an ice cream please",
        help="Try simple, concrete phrases first.",
    )

    manual_gloss = st.text_input(
        "Optional manual gloss override",
        value="",
        help="Example: HELLO ME WANT ICE-CREAM PLEASE. Leave blank to use the rough converter.",
    )

    if manual_gloss.strip():
        gloss_tokens = [normalise_text(t) for t in manual_gloss.split() if normalise_text(t)]
    else:
        gloss_tokens = english_to_rough_gloss(phrase)

    st.subheader("Rough gloss")
    st.code(" ".join(token.upper() for token in gloss_tokens) or "No gloss generated")

    if st.button("Build video sequence", type="primary"):
        if not gloss_tokens:
            st.error("Enter a phrase first.")
            return

        results = [fetch_first_sign(token) for token in gloss_tokens]
        found = sum(1 for r in results if r.video_url)
        st.success(f"Found {found} of {len(results)} videos automatically.")

        for i, result in enumerate(results, start=1):
            render_video(result, i)

    with st.expander("Edit the rough translation rules"):
        st.write("Open `app.py` and edit `PHRASE_MAP`, `WORD_MAP`, and `DROP_WORDS`.")
        st.write("Dictionary lookup uses the `s=` keyword-search parameter, not `s[]=`.")
        st.write("For better NZSL, treat this as a vocabulary sequencer, not grammar authority.")


if __name__ == "__main__":
    main()
