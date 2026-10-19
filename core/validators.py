from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.utils.deconstruct import deconstructible

IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp', 'gif']
VIDEO_EXTENSIONS = ['mp4', 'webm', 'ogg', 'mov', 'm4v']
RESOURCE_EXTENSIONS = [
    'pdf', 'ppt', 'pptx', 'key', 'odp', 'doc', 'docx', 'odt', 'txt', 'md',
    'xls', 'xlsx', 'csv', 'zip', 'png', 'jpg', 'jpeg', 'py', 'ipynb',
]

validate_image_extension = FileExtensionValidator(IMAGE_EXTENSIONS)
validate_video_extension = FileExtensionValidator(VIDEO_EXTENSIONS)
validate_resource_extension = FileExtensionValidator(RESOURCE_EXTENSIONS)


@deconstructible
class MaxFileSizeValidator:
    def __init__(self, setting_name, label='File'):
        self.setting_name = setting_name
        self.label = label

    def __call__(self, file):
        limit = getattr(settings, self.setting_name)
        if file and getattr(file, 'size', 0) > limit:
            raise ValidationError(f'{self.label} must be smaller than {limit // (1024 * 1024)} MB.')

    def __eq__(self, other):
        return (isinstance(other, MaxFileSizeValidator)
                and other.setting_name == self.setting_name and other.label == self.label)


validate_image_size = MaxFileSizeValidator('MAX_IMAGE_UPLOAD_SIZE', 'Image')
validate_video_size = MaxFileSizeValidator('MAX_VIDEO_UPLOAD_SIZE', 'Video')
validate_resource_size = MaxFileSizeValidator('MAX_RESOURCE_UPLOAD_SIZE', 'File')
