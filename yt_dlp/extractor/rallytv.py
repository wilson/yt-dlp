import re

from .common import InfoExtractor
from ..utils import (
    ExtractorError,
    try_get,
)


class RallyTVIE(InfoExtractor):
    """
    Extractor for Rally.TV videos
    """
    _VALID_URL = r'https?://(?:www\.)?rally\.tv/video/(?P<id>[\w-]+)'
    _BASE_URL = 'https://www.rally.tv'
    _API_BASE = 'https://dms.redbull.tv/v5/destination/rallytv'

    _TESTS = [{
        'url': 'https://www.rally.tv/video/3f435f44-b6e2-50de-923d-d8cd8311ddef',
        'info_dict': {
            'id': '3f435f44-b6e2-50de-923d-d8cd8311ddef',
            'ext': 'mp4',
            'title': 'Rally.TV Video 3f435f44-b6e2-50de-923d-d8cd8311ddef',
            'format_id': re.compile(r'.+'),
            'duration': float,
            'height': int,
            'width': int,
        },
        'params': {
            'skip_download': True,
        },
    }]

    _COMMON_HEADERS = {
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Origin': 'https://www.rally.tv',
        'Referer': 'https://www.rally.tv/',
        'Connection': 'keep-alive',
    }

    def _real_extract(self, url):
        video_id = self._match_id(url)
        self.to_screen(f'Extracting video with ID: {video_id}')

        # Set default title
        title = f'Rally.TV Video {video_id}'

        # Use the direct master playlist URL
        formats = []
        master_url = f'{self._API_BASE}/{video_id}/personal_computer/http/us/en_US/playlist.m3u8'
        self.to_screen(f'Attempting to fetch master playlist: {master_url}')

        # Prepare request headers
        headers = self.geo_verification_headers()
        headers.update(self._COMMON_HEADERS)

        try:
            # Extract formats from the master playlist
            master_formats = self._extract_m3u8_formats(
                master_url, video_id, 'mp4',
                entry_protocol='m3u8_native',
                headers=headers,
                m3u8_id='hls',
                fatal=True)

            if master_formats:
                self.to_screen(f'Successfully extracted {len(master_formats)} formats from master playlist')
                formats.extend(master_formats)

        except ExtractorError as e:
            self.report_warning(f'Failed to extract HLS formats: {e}')
        except Exception as e:
            raise ExtractorError(f'Failed to extract video formats: {e}')

        if not formats:
            raise ExtractorError('Could not extract any video formats.')

        # Build the final info dictionary
        return {
            'id': video_id,
            'title': title,
            'formats': formats,
            'thumbnail': try_get(lambda: f'{self._BASE_URL}/thumbnail/{video_id}', str),
        }
