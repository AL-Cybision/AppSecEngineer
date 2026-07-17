from pathlib import Path


def unsafe(upload, storage, fileobj):
    # ruleid: expenseguard.unsafe-upload-filename-path
    storage.put(fileobj, upload.filename, "application/octet-stream")
    # ruleid: expenseguard.unsafe-upload-filename-path
    open(upload.filename, "wb")


def safe(upload, storage, fileobj):
    display_name = Path(upload.filename).name
    storage.put(fileobj, "receipts/6a29177c-6613-45a4-a62c-e39c833c1984.pdf", "application/pdf")
    return display_name
