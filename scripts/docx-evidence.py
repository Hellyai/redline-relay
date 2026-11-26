"""Extract candidate Word body differences and comment evidence as UTF-8 JSON."""
import argparse
from difflib import SequenceMatcher
import json
import sys
from xml.etree import ElementTree as ET
from zipfile import ZipFile

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def visible_text(node):
    if node.tag in (W + "del", W + "moveFrom"):
        return ""
    if node.tag == W + "t":
        return node.text or ""
    if node.tag in (W + "tab", W + "br", W + "cr"):
        return "\t" if node.tag == W + "tab" else "\n"
    return "".join(visible_text(child) for child in node if child.tag != W + "p")


def read_document(path):
    with ZipFile(path) as package:
        root = ET.fromstring(package.read("word/document.xml"))
        comments = {}
        if "word/comments.xml" in package.namelist():
            part = ET.fromstring(package.read("word/comments.xml"))
            for node in part.findall(W + "comment"):
                comments[node.get(W + "id")] = {
                    "author": node.get(W + "author"),
                    "date": node.get(W + "date"),
                    "text": "\n".join(visible_text(p) for p in node.iter(W + "p")),
                }
    paragraphs = []
    for index, p in enumerate(root.find(W + "body").iter(W + "p"), 1):
        anchors = dict.fromkeys(
            child.get(W + "id") for child in p.iter()
            if child.tag in (W + "commentRangeStart", W + "commentReference")
        )
        paragraphs.append({"paragraph": index, "text": visible_text(p),
                           "comment_ids": list(anchors)})
    return {"paragraphs": paragraphs, "comments": comments}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline")
    parser.add_argument("response")
    args = parser.parse_args()
    before = read_document(args.baseline)
    after = read_document(args.response)
    old, new = ([p for p in doc["paragraphs"] if p["text"].strip()]
                for doc in (before, after))
    matcher = SequenceMatcher(None, [p["text"] for p in old],
                              [p["text"] for p in new], autojunk=False)
    changes = [{"kind": kind, "before": old[i:j], "after": new[k:l]}
               for kind, i, j, k, l in matcher.get_opcodes() if kind != "equal"]
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps({"baseline": before, "response": after, "changes": changes},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
