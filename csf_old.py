"""
CSF tools for python 3.13

Made for free use in Command & Conquer

Most of the information in the documentation was taken from:
https://modenc.renegadeprojects.com/CSF_File_Format
"""

from pathlib import Path
from typing import BinaryIO
from struct import unpack_from as unpack, pack
from json import load, dump

class CSF:

    """
    Compiled String Format or CSF is a widely-used file format
    for storing and utilizing labels, descriptions and other text in the projects
    such as games (Command & Conquer)

    CSF file structure in binary encode:

    |  FCS | Ver  | NumL | NumS | null | Lang

    |  LBL | NumP | LenL |      L      |
    |  RTS | LenS |      S      |
    | WRTS | LenS |      S      | LenX |  X   |

    ...

    * Useless means the game may never use this or set to default value

    ######################################################################

    FCS - CSF header identifier.
    If it's not " FSC", the parser will not load the file.
    By the way FCS means CSF in reversed order.

    Ver - CSF version. Useless

    NumL - number of labels in this CSF AKA keys of descriptions.

    NumS - number of strings in this CSF. Mostly the same as NumL.

    null - placeholder for parsing. Useless

    Lang - language of this CSF. See available languages below. Useless

    ######################################################################

    LBL - Label
    """

    def __init__(self, filepath: Path | str = Path("generals.csf")) -> None:
        self.file = filepath

    def read(self) -> str | bytes:
        with open(self.file, "rb") as r:
            return r.read()

    def write_bytes(self, outpath: Path | str = Path("temp.txt")) -> None:
        data = self.read()

        with open(outpath, "w") as w:
            # split the binary data by LBL byte marker
            p = r""
            for rec in data.split(b"\x20\x4c\x42\x4c"):

                # if not rec:
                #     continue

                # Format record bytes into hex values
                h = "".join(f"\\x{b:02x}" for b in rec)

                # Write with record label and newlines
                w.write(f"{p}{h}\n")
                p = r"\x20\x4c\x42\x4c"

    def _line_reader(self, data: bytes) -> tuple[str | None]:

        offset = 0
        if data[offset:offset + 4] != b"\x20\x4c\x42\x4c": # LBL header
            raise ValueError("Invalid Header")

        offset += 4
        NumP, LenL = unpack("<II", data, offset)

        offset += 8
        L = data[offset:offset + LenL].decode("utf-8") # Label L
        offset += LenL

        TypeS, LenS, S, LenX, X = None, 0, "", None, None

        if NumP == 1:
            TypeS = data[offset:offset + 4].decode("latin-1")
            offset += 4
            (LenS,) = unpack("<I", data, offset)

            offset += 4
            encrypted = data[offset:offset + LenS * 2]

            offset += LenS * 2
            decrypted = bytes(b ^ 0xFF for b in encrypted) # Full UTF-16LE XOR Decryption

            # Trim trailing odd byte if padded
            if len(decrypted) % 2 != 0:
                decrypted = decrypted[:-1]

            S = decrypted.decode("utf-16le")

            if TypeS == "WRTS":
                (LenX,) = unpack("<I", data, offset)
                offset += 4
                encrypted = data[offset:offset + LenX * 2]

                offset += LenX * 2
                decrypted = bytes(b ^ 0xFF for b in encrypted)

                if len(decrypted) % 2 != 0:
                    decrypted = decrypted[:-1]

                X = decrypted.decode("utf-16le")

        return L, S, X

    def _write_record(self, w: BinaryIO, key: str, values: list) -> None:

        """
        Write one CSF label record (LBL/RTS/WRTS)
        """

        line = [pack("<4s", b"\x20\x4c\x42\x4c")]

        L = key.encode("utf-8")
        LenL = pack("<I", len(L))

        if not values or values[0] is None: # NumP = 0
            line.extend((pack("<I", 0), LenL, L))
            w.write(b"".join(line))
            return

        line.extend((pack("<I", 1), LenL, L)) # NumP = 1

        # Main
        text_s = values[0]
        encoded_s = text_s.encode("utf-16le")
        encrypted_s = bytes(b ^ 0xFF for b in encoded_s)
        LenS = pack("<I", len(text_s))

        # RTS
        if len(values) == 1 or values[1] is None:
            line.extend((pack("<4s", b"\x20\x52\x54\x53"), LenS, encrypted_s))

        # WRTS
        else:
            text_x = values[1]
            encoded_x = text_x.encode("utf-16le")
            encrypted_x = bytes(b ^ 0xFF for b in encoded_x)
            LenX = pack("<I", len(text_x))

            line.extend((pack("<4s", b"\x57\x52\x54\x53"), LenS, encrypted_s, LenX, encrypted_x))

        w.write(b"".join(line))

    def _iter_records(self):
        """Yield the header and each LBL record as raw bytes."""

        data = self.read()
        first = data.find(b" LBL")

        # Header
        yield data[:first]

        # Records
        start = first
        while start != -1:
            next_start = data.find(b" LBL", start + 4)

            if next_start == -1:
                yield data[start:]
                break

            yield data[start:next_start]
            start = next_start

    def dump_to_json(self, outpath: Path | str, indent: int = 2) -> None:

        d = {"header": {}, "main": {}}

        temp = Path("temp.txt")
        self.write_bytes(temp)

        with open(temp, "r", encoding = "utf-8") as r:
            line = bytes(
                        r.readline().strip().encode("utf-8").decode("unicode_escape"),
                        encoding = "latin-1"
                    )

            Header, Ver, NumL, NumS, _, Lang = unpack("<4sIIIII", line)

            if Header != b" FSC":
                raise ValueError(f"Incorrect CSF file signature: {Header.decode('latin-1')}")

            d["header"]["Ver"] = Ver
            d["header"]["NumL"] = NumL
            d["header"]["NumS"] = NumS
            d["header"]["Lang"] = Lang

            for line in r:
                # print(line)
                L, S, X = self._line_reader(bytes(line.encode("utf-8").decode("unicode_escape"), encoding = "latin-1"))

                d["main"][L] = [S]
                d["main"][L].append(X) if X is not None else None

        with open(outpath, "w", encoding = "utf-8") as f:
            dump(d, f, indent = indent, ensure_ascii = False)

        temp.unlink(missing_ok = True)

    def dump_to_json_simple(self, outpath: Path | str, indent: int = 2) -> None:
        d = {}

        temp = Path("temp.txt")
        self.write_bytes(temp)

        with open(temp, "r", encoding = "utf-8") as r:
            r.readline()
            for line in r:
                # print(line)
                L, S, X = self._line_reader(bytes(line.encode("utf-8").decode("unicode_escape"), encoding = "latin-1"))

                d[L] = [S]
                d[L].append(X) if X is not None else None

        with open(outpath, "w", encoding = "utf-8") as f:
            dump(d, f, indent = indent, ensure_ascii = False)

        temp.unlink(missing_ok = True)

    def load_from_json(self, inpath: Path | str, outpath: Path | str = Path("generals.csf"), simple: bool = False) -> None:

        """
        Docstring for load_from_json

        :param self: Description
        :param inpath: Description
        :type inpath: Path | str
        :param outpath: Description
        :type outpath: Path | str
        :param simple: Description
        :type simple: bool
        """

        with open(inpath, "r") as r:
            data = load(r)

        if not simple:
            header = data["header"]
            main = data["main"]

            with open(outpath, "wb") as w:

                # header line
                w.write(
                    pack("<4s", b"\x20\x46\x53\x43") +  # FSC, file marker
                    pack("<I", header["Ver"]) +         # Ver, useless
                    pack("<I", header["NumL"]) +        # NumL, number of lables
                    pack("<I", header["NumS"]) +        # NumS, number of strings
                    pack("<I", 0) +                     # null, useless
                    pack("<I", header["Lang"])          # Lang, useless
                )

                # main content
                for key, values in main.items():
                    self._write_record(w, key, values)

        else:

            NumL = len(data)
            NumS = sum(1 for s in data.values() if s)

            with open(outpath, "wb") as w:

                # header line
                w.write(
                    pack("<4s", b"\x20\x46\x53\x43") +  # FSC, file marker
                    pack("<I", 3) +                     # Ver, useless
                    pack("<I", NumL) +                  # NumL, number of lables
                    pack("<I", NumS) +                  # NumS, number of strings
                    pack("<I", 0) +                     # null, useless
                    pack("<I", 0)                       # Lang, useless
                )

                # main content
                for key, values in data.items():
                    self._write_record(w, key, values)

# if __name__ == "__main__":
#     file1 = Path("generals.csf")
#     file2 = Path("test2.csf")
#     json_file = Path("test.json")

#     c = CSF(file1)

#     c.dump_to_json(json_file)
#     c.load_from_json(json_file, file2)

#     with open("generals.csf", "rb") as f1, open("test2.csf", "rb") as f2:
#         a = f1.read()
#         b = f2.read()

#     for i, (x, y) in enumerate(zip(a, b)):
#         if x != y:
#             print(f"First difference at offset {i}: {x:02X} != {y:02X}")
#             break

#     print(len(a), len(b))

#     file2.unlink(missing_ok=True)
#     json_file.unlink(missing_ok=True)
