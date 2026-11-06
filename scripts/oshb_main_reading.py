"""Separate direct source words from alternate words inside OSHB notes."""
from build_oshb_subset import NS


def primary_and_note_tokens(verse):
    direct = verse.findall('o:w', NS)
    note_words = verse.findall('.//o:note//o:w', NS)
    all_words = verse.findall('.//o:w', NS)
    allowed = {id(w) for w in direct + note_words}
    if len(allowed) != len(all_words) or any(id(w) not in allowed for w in all_words):
        raise ValueError('Unexpected word wrapper outside verse or note')
    def fields(words):
        return [(w.get('id'), ''.join(w.itertext()), w.get('lemma'), w.get('morph')) for w in words]
    return fields(direct), fields(note_words)
