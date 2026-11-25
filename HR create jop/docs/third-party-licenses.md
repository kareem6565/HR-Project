# Third-party software notices

This file records the OCR components explicitly installed by `backend/Dockerfile`.
The package versions below are the Debian Bookworm versions pinned in that file.
This is an inventory, not a legal opinion or a complete notice for every transitive
operating-system package in the container. The image's Debian package manifest is
the source of truth for the complete binary-package inventory.

| Component | Installed package/version | License recorded for this component | Source and license reference |
| --- | --- | --- | --- |
| Tesseract OCR engine | `tesseract-ocr` `5.3.0-2` | Apache-2.0 | [Upstream source and LICENSE](https://github.com/tesseract-ocr/tesseract) |
| Tesseract English language data | `tesseract-ocr-eng` `1:4.1.0-2` | Apache-2.0 | [Official trained-data repositories and license information](https://github.com/tesseract-ocr/tessdata_fast) |
| Tesseract Arabic language data | `tesseract-ocr-ara` `1:4.1.0-2` | Apache-2.0 | [Official trained-data repositories and license information](https://github.com/tesseract-ocr/tessdata_fast) |
| Tesseract orientation/script data | `tesseract-ocr-osd` `1:4.1.0-2` | Apache-2.0 | [Official trained-data repositories and license information](https://github.com/tesseract-ocr/tessdata_fast) |
| Leptonica image processing library (Tesseract dependency) | Debian dependency; version supplied by the pinned Debian Bookworm package set | BSD-2-Clause | [Upstream source](https://github.com/DanBloomberg/leptonica) and [license reference](https://www.leptonica.org/about-the-license.html) |
| Poppler PDF rasterizer (`pdftoppm`, from `poppler-utils`) | `22.12.0-2+deb12u3` | GPL-2-or-later (Poppler is GPL-licensed; Debian package metadata is authoritative for the shipped build) | [Upstream source](https://gitlab.freedesktop.org/poppler/poppler) and [Poppler project site](https://poppler.freedesktop.org/) |

## Source availability note

Poppler is distributed under GPL terms. The corresponding source is available from
the Poppler upstream repository and from Debian's source-package archive for the
Debian package version listed above. The project should keep the source corresponding
to the shipped Debian build identifiable and available with the distribution, along
with applicable notices. This note records source locations; it does not state a
legal conclusion about distribution obligations.

The OCR flow invokes Poppler's `pdftoppm` executable as a separate process. The
application does not link Poppler as an in-process library. No AGPL component is
intentionally installed for OCR.

## References checked

- Tesseract upstream license: <https://github.com/tesseract-ocr/tesseract/blob/main/LICENSE>
- Official fast trained-data repository license: <https://github.com/tesseract-ocr/tessdata_fast>
- Leptonica license reference: <https://www.leptonica.org/about-the-license.html>
- Poppler upstream repository: <https://gitlab.freedesktop.org/poppler/poppler>
