# -*- coding: utf-8 -*-
"""Lớp NLP của mô-đun 1 (Fig. 1): spaCy POS tagging + gazetteer cho NER.

- Gazetteer (G) được nạp vào EntityRuler của spaCy, gắn nhãn RESOURCE/NETWORK.
- POS tagging dùng để loại các phân từ làm bổ ngữ ("registered courses",
  "issued agreements") và danh từ ("a contract number") khỏi danh sách hành động.

spaCy là tuỳ chọn: nếu chưa cài (hoặc đặt ABAC_DISABLE_SPACY=1), `annotate`
trả None và rules.py dùng regex tương đương.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

MODELS = ("en_core_web_md", "en_core_web_sm")

_STATE: dict = {"nlp": None, "loaded": False, "gazetteer": None}


@dataclass
class Annotation:
    entities: list[tuple[str, str, int, int]] = field(default_factory=list)  # (label, id, start, end)
    modifier_starts: set[int] = field(default_factory=set)                   # token không phải hành động


def available() -> bool:
    return _load() is not None


def configure(gazetteer: dict[str, list[tuple[str, str]]]) -> None:
    """Đăng ký gazetteer {label: [(cụm từ, id)]}; nạp lại EntityRuler nếu cần."""
    _STATE["gazetteer"] = gazetteer
    nlp = _load()
    if nlp is not None:
        _install_ruler(nlp, gazetteer)


def annotate(text: str) -> Annotation | None:
    nlp = _load()
    if nlp is None:
        return None
    doc = nlp(text)
    ann = Annotation()
    for ent in doc.ents:
        if ent.label_ in ("RESOURCE", "NETWORK"):
            ann.entities.append((ent.label_, ent.ent_id_, ent.start_char, ent.end_char))
    for tok in doc:
        if _is_non_action(tok):
            ann.modifier_starts.add(tok.idx)
    return ann


def _is_non_action(tok) -> bool:
    """Phân từ làm bổ ngữ ("registered courses") hoặc danh từ ("a contract number")."""
    if tok.dep_ == "amod" and tok.tag_ in ("VBN", "VBD"):
        return True
    if tok.pos_ == "ADJ" and tok.text.endswith("ed"):
        return True
    return tok.pos_ == "NOUN" and tok.dep_ in ("dobj", "pobj", "nsubj", "compound")


def _load():
    if _STATE["loaded"]:
        return _STATE["nlp"]
    _STATE["loaded"] = True
    if os.environ.get("ABAC_DISABLE_SPACY") == "1":
        return None
    try:
        import spacy
    except ImportError:
        return None
    for name in MODELS:
        try:
            nlp = spacy.load(name)
            break
        except OSError:
            continue
    else:
        return None
    _STATE["nlp"] = nlp
    if _STATE["gazetteer"]:
        _install_ruler(nlp, _STATE["gazetteer"])
    return nlp


def _install_ruler(nlp, gazetteer: dict[str, list[tuple[str, str]]]) -> None:
    if "abac_gazetteer" in nlp.pipe_names:
        nlp.remove_pipe("abac_gazetteer")
    ruler = nlp.add_pipe("entity_ruler", name="abac_gazetteer", before="ner",
                         config={"phrase_matcher_attr": "LOWER", "overwrite_ents": True})
    patterns = []
    for label, phrases in gazetteer.items():
        for phrase, ent_id in phrases:
            patterns.append({"label": label, "pattern": phrase, "id": ent_id})
    ruler.add_patterns(patterns)


def reset() -> None:
    """Dùng trong test: buộc nạp lại (vd. sau khi đổi ABAC_DISABLE_SPACY)."""
    _STATE.update(nlp=None, loaded=False)
