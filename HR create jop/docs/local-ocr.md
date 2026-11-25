# Local OCR for scanned resumes

Scanned PDFs with no usable text layer are OCRed in the screening worker only. The worker passes the decrypted PDF bytes to Poppler over stdin; it does not write the PDF to disk. Poppler writes one page image at a time in a private temporary directory (mode `0700` on Linux), and the directory is removed after success, error, or timeout. Tesseract receives the raster through stdin. No cloud OCR service is configured or called.

The existing `MAX_PDF_PAGES` cap applies before rasterization. Rendering is capped to a 2400-pixel long edge. `OCR_PAGE_TIMEOUT_SECONDS=20` limits each Poppler/Tesseract process, `OCR_FILE_TIMEOUT_SECONDS=180` bounds the complete PDF, and `OCR_MAX_CONCURRENT_JOBS=1` bounds OCR per backend process (the current worker is one thread per application process). Timed-out subprocesses are killed. `OCR_CONFIDENCE_THRESHOLD=0.55` is the default threshold; set an appropriate value for your deployment after validating representative printed scans.

The worker records `extraction_source` (`text_layer` or `ocr`) and OCR confidence from Tesseract TSV word confidences (0–1). Below threshold, the resume status is `needs_manual_review`, shown in the application review screen with the confidence value. The existing AI evaluation may still run, but this state never records an HR decision or auto-rejects a candidate. No readable OCR text is a visible extraction failure, not an empty success.

## Components and licenses

| Component | Pinned distribution | License | Reason |
| --- | --- | --- | --- |
| Tesseract OCR | Debian Bookworm `tesseract-ocr=5.3.0-2` | Apache-2.0; Leptonica dependency is BSD-2-Clause | Local printed-text OCR with word-level confidence |
| English, Arabic, orientation data | `tesseract-ocr-eng=1:4.1.0-2`, `tesseract-ocr-ara=1:4.1.0-2`, `tesseract-ocr-osd=1:4.1.0-2` | Apache-2.0 | Debian packages the fast integerized models; lower CPU and storage cost than `tessdata_best`; OSD is required by Tesseract |
| PDF rasterizer | `poppler-utils=22.12.0-2+deb12u3`, invoked as `pdftoppm` CLI | GPL-2-or-later | Separate process reads PDF bytes from stdin; no AGPL Python PDF library is added |

The Debian Bookworm package metadata reports 2.135 MB for the Tesseract CLI, 4.032 MB for English data, 1.414 MB for Arabic data, 10.331 MB for orientation data, and 0.716 MB for `poppler-utils` on amd64: 18.628 MB of direct installed packages, plus their shared-library dependencies. The measured full Docker image delta was 151,606,492 bytes (144.54 MiB): the pre-OCR image was 1,158,466,955 bytes and the OCR image was 1,310,073,447 bytes. This includes the rasterizer, Tesseract, language data, and their image-layer dependencies. The direct package installed-size sum is 18.628 MB; it is not the full image delta. The base image is pinned to the Bookworm variant so these package versions remain available from the matching Debian suite.

The fast Arabic model is intended for printed text. Quality on real Arabic scans, handwriting, low-resolution pages, stamps, skew, and unusual fonts has not been measured; HR must check the original CV whenever confidence is below threshold, and should spot-check OCR output in all cases.

The CI backend job installs Tesseract, English/Arabic language packs, and Poppler before running the extraction tests. OCR tests do not silently skip when a system tool is missing.
