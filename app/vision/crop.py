import logging
from typing import Tuple, List
from PIL import Image

from app.vision.template_matcher import DynamicTemplateMatcher

logger = logging.getLogger(__name__)

# Global Dynamic Template Matcher Instance using sample templates
_template_matcher = DynamicTemplateMatcher()


def crop_dynamic_templates(img: Image.Image) -> Tuple[List[Image.Image], List[Image.Image]]:
    """Dynamically detect Small Code pills and Large Code banners using registered template matcher module."""
    return _template_matcher.match_templates(img)
