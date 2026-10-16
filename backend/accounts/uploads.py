"""Stop oversized uploads while streaming, before writing the full file to disk."""
from django.core.exceptions import RequestDataTooBig
from django.core.files.uploadhandler import FileUploadHandler


class SizeLimitHandler(FileUploadHandler):
    maximum = 5 * 1024 * 1024

    def __init__(self, request=None):
        super().__init__(request)
        self.received = 0

    def handle_raw_input(self, input_data, META, content_length, boundary, encoding=None):
        if content_length is not None and content_length > self.maximum + 1024 * 1024:
            raise RequestDataTooBig('Upload request exceeds size limit.')

    def receive_data_chunk(self, raw_data, start):
        self.received += len(raw_data)
        if self.received > self.maximum:
            raise RequestDataTooBig('Upload exceeds 5 MB.')
        return raw_data

    def file_complete(self, file_size):
        return None  # The following Django handler constructs the uploaded file.
