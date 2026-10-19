"""Sends private files from MEDIA_ROOT. Handles Range requests so video seeking works."""
import mimetypes
import os
import re

from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse

_RANGE = re.compile(r'bytes=(\d*)-(\d*)')
_CHUNK = 64 * 1024


def _iter_range(path, start, length):
    with open(path, 'rb') as fh:
        fh.seek(start)
        remaining = length
        while remaining > 0:
            data = fh.read(min(_CHUNK, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data


def serve_file(request, field_file, as_attachment=False):
    if not field_file:
        raise Http404
    try:
        path = field_file.path
    except NotImplementedError:
        raise Http404
    if not os.path.exists(path):
        raise Http404('File missing')
    size = os.path.getsize(path)
    content_type = mimetypes.guess_type(path)[0] or 'application/octet-stream'
    filename = os.path.basename(path)

    match = _RANGE.match(request.headers.get('Range', ''))
    if match and not as_attachment:
        start_s, end_s = match.groups()
        if start_s:
            start = int(start_s)
            end = int(end_s) if end_s else size - 1
        else:  # suffix range: last N bytes
            start = max(size - int(end_s or 0), 0)
            end = size - 1
        end = min(end, size - 1)
        if start > end or start >= size:
            response = HttpResponse(status=416)
            response['Content-Range'] = f'bytes */{size}'
            return response
        length = end - start + 1
        response = StreamingHttpResponse(_iter_range(path, start, length), status=206, content_type=content_type)
        response['Content-Length'] = str(length)
        response['Content-Range'] = f'bytes {start}-{end}/{size}'
    else:
        response = FileResponse(open(path, 'rb'), content_type=content_type,
                                as_attachment=as_attachment, filename=filename)
    response['Accept-Ranges'] = 'bytes'
    response['Cache-Control'] = 'private, max-age=0'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
