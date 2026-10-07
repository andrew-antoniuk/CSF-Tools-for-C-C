"""
CSF tools for Python 3+

Check out the article about CSF: https://modenc.renegadeprojects.com/CSF_File_Format
"""

from pathlib import Path
from io import BufferedReader
from struct import unpack, pack
from json import dump, load
from os import remove

DEFAULT_PATH = Path("generals.csf")

class CSF:

    def __init__(self, filepath: Path = DEFAULT_PATH) -> None:
        self.update(filepath)

    def update(self, newfile: Path) -> None:

        """
        Used for creating an instance of the object and updating it later.
        Delegates metadata assignment to read_header(...), which reads the file.csf header and returns the values from it.
        Does not create the object with wrong signature of the file.
        """

        self.__ver, self.__numl, self.__nums, self.__lang = self.read_header(newfile)
        self.__file = newfile

    def read_header(self, filepath: Path) -> tuple[int, int, int, int]:

        with open(filepath, "rb") as f:
            header = f.read(24)

        SIGN, Ver, NumL, NumS, _, Lang = unpack("<4sIIIII", header)

        if SIGN != b" FSC":
            raise ValueError("Incorrect file format")

        return Ver, NumL, NumS, Lang

    def current_path(self) -> str:
        return str(self.__file)

    def metadata(self) -> tuple[int, int, int, int]:

        """
        Get 4-tuple consisting of:

            Ver: Version of CSF
            NumL: Number of Lines
            NumS: Number of Strings
            Lang: Language (0 is default US/UK)

        Make sure your class data was updated with self.update()!
        """

        return self.__ver, self.__numl, self.__nums, self.__lang

    def write_to_markdown(self) -> None:
        pass

    def dump_to_json(self, dump_path: Path = Path("generals.json"), indentation: int = 4) -> None:

        self.update(self.__file)

        def read_u32(f: BufferedReader):
            return int.from_bytes(f.read(4), "little")

        def decode_string(data: bytes) -> str:
            data = bytes(byte ^ 0xFF for byte in data)
            return data.decode("utf-16-le")

        json_csf = {

            "METADATA": {
                "Ver": self.__ver,
                "NumL": self.__numl,
                "NumS": self.__nums,
                "Lang": self.__lang
            },

            "LABEL": {

            }

        }

        with open(self.__file, "rb") as r:
            r.read(24) # header skip
            for i in range(self.__numl):
                try:
                    r.read(4)

                    NumP = read_u32(r)
                    LenL = read_u32(r)
                    L = r.read(LenL).decode("utf-8", errors = "ignore")

                    if NumP != 1:
                        json_csf["LABEL"][L] = {"STR": ""}
                        continue

                    S_TYPE = r.read(4)
                    LenS = read_u32(r)
                    S = r.read(LenS * 2)

                    json_csf["LABEL"][L] = {"STR": decode_string(S)}

                    if S_TYPE == b"WRTS":
                        LenX = read_u32(r)
                        X = r.read(LenX)

                        json_csf["LABEL"][L]["EXTRA"] = X.decode("utf-8")

                except Exception as e:
                    print(f"Error: {e.args[0]}")
                    print(F"Iteration: {i}")
                    print(L, S, X if S_TYPE == b"WRTS" else "")

        with open(dump_path, "w", encoding = "utf-8") as w:
            dump(json_csf, w, indent = indentation)

    def load_from_json(self, load_path: Path = Path("generals.json"), outpath: Path = Path("generals.csf")) -> None:
        with open(load_path, "r") as r:
            json_csf = load(r)

        with open(outpath, "wb") as w:

            w.write(
                pack("<4s", b"\x20\x46\x53\x43") +  # FSC, file marker
                pack("<I", self.__ver) +         # Ver, useless
                pack("<I", self.__numl) +        # NumL, number of lables
                pack("<I", self.__nums) +        # NumS, number of strings
                pack("<I", 0) +                     # null, useless
                pack("<I", self.__lang)          # Lang, useless
            )

            try:
                for key, values in json_csf["LABEL"].items():
                    pairs = 1 if values["STR"] else 0
                    NumP = pack("<I", pairs)
                    L = bytes(b ^ 0xFF for b in key.encode("utf-16le"))
                    line: bytes = pack("<4s", b"\x20\x4c\x42\x4c") + NumP + pack("<I", len(key)) + pack("<4s", L)

                    if pairs:
                        S_TYPE = b"\x20\x52\x54\x53" if "EXTRA" not in values else b"\x57\x52\x54\x53"
                        S = bytes(b ^ 0xFF for b in values["STR"].encode("utf-16le"))
                        line += pack("<4s", S_TYPE) + pack("<I", len(values["STR"])) + pack("<4s", S)

                        if S_TYPE == b"\x57\x52\x54\x53":
                            X = bytes(b ^ 0xFF for b in values["EXTRA"].encode("utf-16le"))
                            line += pack("<I", len(values["EXTRA"])) + pack("<4s", X)

                w.write(line)

            except Exception as e:
                print(e.args[0])
                remove(outpath)
                return

        self.update(outpath)


c = CSF()
c.dump_to_json()
# c.load_from_json(outpath = Path("t.csf"))
