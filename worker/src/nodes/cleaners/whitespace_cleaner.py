import re

from nodes.cleaners.base_cleaner import BaseCleaner

_TRAILING_WS = re.compile(r"[ \t]+\n")
_MULTI_BLANK = re.compile(r"\n{3,}")


class WhitespaceCleaner(BaseCleaner):
    @property
    def node_name(self) -> str:
        return "whitespace_cleaner"

    def process(self, text: str) -> str:
        text = _TRAILING_WS.sub("\n", text)
        text = _MULTI_BLANK.sub("\n\n", text)
        return text.strip()


if __name__ == "__main__":
    # Standalone test: run from worker/src with
    #   python3 -m nodes.cleaners.whitespace_cleaner path/to/file.txt
    import argparse

    parser = argparse.ArgumentParser(description="Clean whitespace in a text file and print the result.")
    parser.add_argument("file_path")
    args = parser.parse_args()

    with open(args.file_path, "r", encoding="utf-8", errors="ignore") as f:
        raw = f.read()

    print(WhitespaceCleaner().process(raw))
